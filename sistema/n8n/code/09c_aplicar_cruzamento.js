// Aplica o cruzamento item × catálogo. Valida que todo código escolhido existe entre os candidatos
// (a IA não pode inventar código) e calcula o preço unitário sugerido a partir da tabela.
const prep = $('Montar prompt · Cruzamento').item.json;
const r = $input.item.json || {};
const entrada = prep.cruzamento_entrada || {};
const avisos = [];
if (entrada.erro) avisos.push('Catálogo/pré-seleção indisponível: ' + entrada.erro);

let ia = null;
if (prep.tem_itens) {
  try {
    if (r.error) throw new Error(JSON.stringify(r.error).slice(0, 200));
    const t = (r.content || []).filter(c => c.type === 'text').map(c => c.text).join('');
    const limpo = t.replace(/^```json\s*|```\s*$/g, '').trim();
    ia = JSON.parse(limpo.slice(limpo.indexOf('{'), limpo.lastIndexOf('}') + 1));
  } catch (e) {
    avisos.push('Agente de cruzamento indisponível (' + e.message + ') — sugestões apenas por similaridade, conferir item a item.');
  }
}
const porNumero = Object.fromEntries(((ia && ia.itens) || []).map(x => [String(x.numero), x]));
const ordemTabela = t => { const i = Object.keys(entrada.catalogos || {}).indexOf(t); return i < 0 ? 99 : i; };
const num = v => (v === null || v === undefined || v === '' || isNaN(Number(v))) ? null : Number(v);

const itens = (entrada.itens || []).map(it => {
  const decisao = porNumero[String(it.numero)] || {};
  const ofertas = {};
  for (const [emp, lista] of Object.entries(it.candidatos || {})) {
    const d = decisao[emp];
    let c = null, veredito, justificativa, divergencias = [];
    if (d && d.codigo !== null && d.codigo !== undefined) {
      c = (lista || []).find(x => String(x.codigo) === String(d.codigo));
      if (!c) { veredito = 'VERIFICAR'; justificativa = `IA indicou código ${d.codigo}, que não está entre os candidatos — descartado.`; }
    }
    if (d && c) { veredito = d.veredito || 'VERIFICAR'; justificativa = d.justificativa || ''; divergencias = d.divergencias || []; }
    else if (d && !veredito) { veredito = d.veredito || 'NAO_ATENDE'; justificativa = d.justificativa || 'Nenhum candidato atende.'; }
    else if (!d && Object.keys(decisao).length) { // a IA avaliou o item e não indicou produto desta empresa
      veredito = 'NAO_ATENDE'; justificativa = 'Agente de IA não indicou produto compatível nesta tabela.';
    }
    else if (!d && (lista || []).length && lista[0].score >= 0.45) { // sem decisão da IA: só similaridade alta, para conferência
      c = lista[0]; veredito = 'VERIFICAR'; justificativa = `Sugestão automática por similaridade (${c.score}) — não avaliada pela IA.`;
    }
    if (!c && !veredito) continue;
    const porEmb = num(d && d.itens_por_embalagem) || 1;
    const converter = !!(d && d.converter_para_unidade) && porEmb > 1;
    const preco = c ? num(c.preco) : null;
    ofertas[emp] = {
      codigo: c ? c.codigo : null, descricao: c ? c.descricao : null, marca: c ? c.marca : null,
      preco_tabela: preco, itens_por_embalagem: porEmb, converter_para_unidade: converter,
      preco_unitario_sugerido: preco ? Math.round((converter ? preco / porEmb : preco) * 10000) / 10000 : null,
      sem_preco: !!c && !preco, veredito, justificativa, divergencias,
      alternativas: (lista || []).filter(x => !c || x.codigo !== c.codigo).slice(0, 3).map(x => `${x.codigo} · ${x.descricao} · ${x.marca}`),
    };
  }
  // produto que entra na proposta: escolha da IA (se válida) ou melhor veredito / menor preço / ordem das tabelas
  const RANK = { ATENDE: 3, ATENDE_PARCIAL: 2, VERIFICAR: 1 };
  const validas = Object.entries(ofertas).filter(([, o]) => o.codigo && RANK[o.veredito]);
  let escolha = decisao.escolha && ofertas[decisao.escolha] && ofertas[decisao.escolha].codigo && RANK[ofertas[decisao.escolha].veredito] ? decisao.escolha : null;
  if (!escolha && validas.length) {
    validas.sort(([ea, a], [eb, b]) => (RANK[b.veredito] - RANK[a.veredito])
      || ((a.preco_unitario_sugerido || Infinity) - (b.preco_unitario_sugerido || Infinity))
      || (ordemTabela(ea) - ordemTabela(eb)));
    escolha = validas[0][0];
  }
  return {
    escolha, lote: it.lote || '',
    numero: it.numero, descricao: it.descricao, quantidade: it.quantidade, unidade: it.unidade,
    valor_unitario_estimado: it.valor_unitario_estimado, marca_referencia: it.marca_referencia, origem: it.origem,
    ofertas, recomendacao: decisao.recomendacao || '',
  };
});

if (!(entrada.itens || []).length) avisos.push('Itens do edital não obtidos (PNCP/edital) — cruzamento e proposta prévia sem itens.');
const analise = { ...prep.analise };
analise.cruzamento = {
  catalogos: entrada.catalogos || {}, total_itens: entrada.total_itens || 0, itens,
  observacoes: (ia && ia.observacoes_gerais) || [], avisos, por_ia: !!ia,
};
return { json: { pasta_rel: prep.pasta_rel, rec: prep.rec, analise } };
