// Simula a captação: loop p1 → fila demais → loop demais → consolidar, com 429 injetado.
const fs = require('fs');
const assert = require('assert');
const wf = JSON.parse(fs.readFileSync(__dirname + '/LICITACOES_PNCP_IA.json'));
const code = Object.fromEntries(wf.nodes.filter(n => n.type === 'n8n-nodes-base.code').map(n => [n.name, n.parameters]));
// fixa a data de execução para o teste não depender do dia em que roda (amostra montada para 11/10/2026)
code['Configuração'] = { jsCode: code['Configuração'].jsCode.replace('dataExecucao: null', "dataExecucao: '2026-10-11'") };
const amostra = JSON.parse(fs.readFileSync(__dirname + '/../testes/amostra_pncp.json'));
const saidas = {};
const $ = nome => ({ all: () => saidas[nome].map(json => ({ json })), first: () => ({ json: saidas[nome][0] }) });
let chamadas = 0, injetar429 = 2;
const ctx = { helpers: { httpRequest: async (o) => {
  chamadas++;
  if (injetar429-- > 0) return { statusCode: 429, body: '<html>Limite de Requisições Excedido</html>' };
  const { uf, pagina } = o.qs;
  if (pagina === 1) return { statusCode: 200, body: amostra.paginas1[uf] };
  return { statusCode: 200, body: amostra.demais[0] };
} } };
async function run(nome, entrada, porItem) {
  const f = new Function('$', '$input', `return (async () => {${code[nome].jsCode}\n})()`);
  if (!porItem) { const r = await f.call(ctx, $, { all: () => entrada.map(json => ({ json })) }); return (saidas[nome] = r.map(i => i.json)); }
  const out = [];
  for (const it of entrada) out.push((await f.call(ctx, $, { item: { json: it } })).json);
  return (saidas[nome] = out);
}
async function loop(nomeConsulta, fila) {
  const done = [];
  for (const it of fila) {
    if (it.sentinela) { done.push(it); continue; }
    let r = (await run(nomeConsulta, [it], true))[0];
    while (r.repetir) { r = (await run(nomeConsulta, [r], true))[0]; } // Aguardar → consultar de novo
    done.push(r);
  }
  return done;
}
(async () => {
  const cfg = await run('Configuração', [{}]);
  cfg[0].pncp.pausaEntrePaginasMs = 0;
  console.log('janela', cfg[0].janela.rotulo, '| filtros', cfg[0].filtros.length);
  const fila1 = await run('Fila · página 1', []);
  const p1 = await loop('PNCP · consultar página 1', fila1);
  console.log('p1:', p1.map(p => `${p.uf}:${p.status}/t${p.tentativa}/m${p.matches.length}`).join(' '));
  const filaD = await run('Fila · demais páginas', p1);
  console.log('fila demais:', filaD.length, 'p1 anexado:', !!filaD[0].p1);
  const d = await loop('PNCP · consultar demais páginas', filaD);
  const sel = await run('Consolidar + Filtros', d);
  console.log('selecionados:', sel.length, sel[0].estatisticas);
  console.log(sel.map(s => `${s.uf} ${s.dataEncerramentoProposta} ${s.termos.join('|')} :: ${s.objetoCompra.slice(0, 50)}`).join('\n'));
  fs.writeFileSync(__dirname + '/../testes/sel_teste.json', JSON.stringify(sel));
  assert.equal(sel.length, 4);
  assert.ok(chamadas >= 9);
  console.log('CAPTAÇÃO OK — chamadas HTTP:', chamadas);
})().catch(e => { console.error('FALHOU', e); process.exit(1); });
