// Simulador mínimo do runtime do Code node do n8n para testar o fluxo ponta a ponta com respostas simuladas.
const fs = require('fs');
const wf = JSON.parse(fs.readFileSync(__dirname + '/LICITACOES_PNCP_IA.json'));
const code = Object.fromEntries(wf.nodes.filter(n => n.type === 'n8n-nodes-base.code').map(n => [n.name, n.parameters]));
// data de execução fixa: o teste não depende do dia em que roda (amostra montada para 11/10/2026)
code['Configuração'] = { ...code['Configuração'], jsCode: code['Configuração'].jsCode.replace('dataExecucao: null', "dataExecucao: '2026-10-11'") };
const saidas = {};          // nome -> array de itens (json)
let itemAtual = {};          // para $('X').item em modo por item

function $(nome) {
  if (!(nome in saidas)) throw new Error(`Nó "${nome}" não executou`);
  return {
    all: () => saidas[nome].map(json => ({ json })),
    first: () => ({ json: saidas[nome][0] }),
    get item() { return { json: saidas[nome][itemAtual[nome] ?? 0] }; },
  };
}
async function roda(nome, entrada, idx = 0) {
  const p = code[nome];
  const porItem = p.mode === 'runOnceForEachItem';
  const f = new Function('$', '$input', `return (async () => {${p.jsCode}\n})()`);
  if (!porItem) {
    const r = await f($, { all: () => entrada.map(json => ({ json })), first: () => ({ json: entrada[0] }) });
    saidas[nome] = r.map(i => i.json);
    return saidas[nome];
  }
  const out = [];
  for (let i = 0; i < entrada.length; i++) {
    const r = await f($, { item: { json: entrada[i] } });
    out.push(r.json);
  }
  saidas[nome] = out;
  return out;
}
module.exports = { roda, saidas, setItem: (n, i) => { itemAtual[n] = i; } };

if (require.main === module) (async () => {
  const assert = require('assert');
  const pncp = JSON.parse(fs.readFileSync(process.argv[2] || __dirname + '/../testes/amostra_pncp.json'));
  const cfg = await roda('Configuração', [{}]);
  console.log('janela', cfg[0].janela);
  const sel = JSON.parse(fs.readFileSync(__dirname + '/../testes/sel_teste.json'));
  saidas['Consolidar + Filtros'] = sel;
  // triagem
  const tp = await roda('Montar prompt · Triagem', sel);
  assert.ok(tp[0].body.contents[0].parts[0].text.length > 10);
  saidas['Agente Triagem · Gemini'] = [{ candidates: [{ content: { parts: [{ text: JSON.stringify({ resultados: sel.map((s, i) => ({ id: i, relevancia: i % 4 === 3 ? 'DESCARTAR' : 'ALTA', motivo: 'teste' })) }) }] } }] }];
  const tri = await roda('Aplicar triagem', saidas['Agente Triagem · Gemini']);
  const paraAnalise = await roda('Selecionar para análise', tri);
  console.log('para análise', paraAnalise.length, 'de', tri.length);
  // loop — 2 processos, um com sucesso total e outro com falha do Claude
  const retornos = [];
  for (let k = 0; k < Math.min(2, paraAnalise.length); k++) {
    saidas['Loop · processos'] = [paraAnalise[k]];
    const prep = { relativo: `${paraAnalise[k].uf}/X/Y`, texto: '[[edital.pdf | página 1]]\nA proposta terá validade de 60 dias. DECLARAÇÃO de que não emprega menor.', itens: [{ numero: 1, descricao: 'Reagente' }], avisos: [] };
    saidas['Worker · pastas + downloads'] = [prep];
    await roda('Montar prompt · Analista', [prep]);
    const analista = { resumo: 'ok', relevancia: 'ALTA', prazos: { validade_proposta: { valor: '60 dias', fonte: 'edital.pdf · pág. 1' } }, declaracoes: [{ nome: 'Declaração de não emprego de menor' }] };
    const g = [{ candidates: [{ content: { parts: [{ text: JSON.stringify(analista) }] } }] }];
    await roda('Montar prompt · Auditor', g);
    const claude = k === 0 ? [{ content: [{ type: 'text', text: '```json\n' + JSON.stringify({ ...analista, auditoria: { confianca: 'ALTA', divergencias: [] } }) + '\n```' }] }] : [{ error: { message: 'overloaded' } }];
    const ca = await roda('Consolidar análise', claude);
    const rv = await roda('Aplicar revisão', ca); // revisor desativado = pass-through
    // cruzamento com DUAS tabelas de preço (nomes vindos dos arquivos em _CATALOGOS)
    const cand = { catalogos: { TABELA_PRINCIPAL: { arquivo: 'Tabela Principal.xlsx', produtos: 3, nome: 'Tabela Principal' },
                                DISTRIBUIDOR_X: { arquivo: 'Distribuidor X.xlsx', produtos: 2, nome: 'Distribuidor X' } },
      total_itens: 1, itens: [{ numero: '1', descricao: 'Reagente para glicose 500 mL', quantidade: 10, unidade: 'FR', valor_unitario_estimado: 90,
        candidatos: { TABELA_PRINCIPAL: [{ codigo: 'A1', descricao: 'GLICOSE ENZ 1X500ML', marca: 'M1', preco: 80, score: 0.8 }],
                      DISTRIBUIDOR_X: [{ codigo: 'B7', descricao: 'GLICOSE 2X250ML', marca: 'M2', preco: 70, score: 0.6 }] } }] };
    const mc = await roda('Montar prompt · Cruzamento', [cand]);
    assert.ok(mc[0].tem_itens);
    assert.ok(mc[0].body.system.includes('TABELA_PRINCIPAL (Tabela Principal)') && mc[0].body.system.includes('DISTRIBUIDOR_X'));
    const decisao = k === 0
      ? { itens: [{ numero: '1', TABELA_PRINCIPAL: { codigo: 'A1', veredito: 'ATENDE', justificativa: 'ok' },
                    DISTRIBUIDOR_X: { codigo: 'INVENTADO', veredito: 'ATENDE' }, escolha: 'DISTRIBUIDOR_X' }] }
      : null;
    const ac = await roda('Aplicar cruzamento', [decisao ? { content: [{ type: 'text', text: JSON.stringify(decisao) }] } : { error: { message: 'timeout' } }]);
    const cz = ac[0].analise.cruzamento;
    if (k === 0) {
      assert.equal(cz.itens[0].ofertas.DISTRIBUIDOR_X.veredito, 'VERIFICAR', 'código inventado pela IA deve ser descartado');
      assert.equal(cz.itens[0].escolha, 'TABELA_PRINCIPAL', 'escolha inválida da IA cai para a melhor oferta válida');
    } else {
      assert.ok(cz.avisos.some(a => a.includes('indisponível')));
      assert.equal(cz.itens[0].escolha, 'DISTRIBUIDOR_X', 'sem IA e mesmo veredito: vence o menor preço');
    }
    await roda('Retornar ao loop', [{ resumo: 'gravado', declaracoes: ['01_X.docx'] }]);
    retornos.push(saidas['Retornar ao loop'][0]);
    console.log('loop', k, 'confiança', rv[0].analise.auditoria.confianca, 'avisos', rv[0].analise.auditoria.avisos);
  }
  const pl = await roda('Montar payload · Relatório', retornos);
  console.log('payload: oportunidades', pl[0].oportunidades.length, 'com análise', pl[0].oportunidades.filter(o => o.analise && o.analise.declaracoes).length);
  console.log('avisos', pl[0].avisos);
  assert.equal(pl[0].empresa, 'Sua Empresa');
  saidas['Montar payload · Relatório'] = pl;
  const env = await roda('Envios por destinatário', []);
  assert.ok(env.length >= 1 && env[0].payload.ufs_filtro.length >= 1);
  fs.writeFileSync(__dirname + '/../testes/payload_relatorio.json', JSON.stringify(pl[0], null, 1));
  console.log('TESTE OK');
})().catch(e => { console.error('FALHOU', e); process.exit(1); });
