// Consulta UMA página do PNCP com controle de taxa e já aplica janela + situação + filtros por palavra-chave.
// Se o PNCP devolver 429/5xx/timeout, marca "repetir" com espera progressiva (nó Aguardar) — sem perder a página.
function normalizar(txt) {
  return String(txt || '').normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase()
    .replace(/[^a-z0-9\-\/ ]+/g, ' ').replace(/\s+/g, ' ').trim();
}
function termoParaRegex(termo, exato) {
  const partes = normalizar(termo).split(' ').filter(Boolean).map(p => p.replace(/[.*+?^${}()|[\]\\\/-]/g, '\\$&'));
  if (!partes.length) return null;
  return new RegExp('(?:^|[^a-z0-9])' + partes.join('(?:\\s+[a-z]{1,4}){0,2}\\s+') + (exato ? '(?![a-z0-9])' : ''), 'i');
}
function compilar(filtros) {
  const c = (r, ex) => (r || []).map(t => ({ t, re: termoParaRegex(t, ex) })).filter(x => x.re);
  return filtros.map(f => ({ id: f.id, chave: c(f.chave, f.exato), comp: c(f.complementares), excl: c(f.exclusoes) }));
}
function avaliar(texto, comp) {
  const n = ' ' + normalizar(texto) + ' ';
  const hits = [], termos = new Set();
  for (const f of comp) {
    const k = f.chave.find(x => x.re.test(n));
    if (!k) continue;
    let c = null;
    if (f.comp.length) { c = f.comp.find(x => x.re.test(n)); if (!c) continue; }
    if (f.excl.some(x => x.re.test(n))) continue;
    hits.push(f.id);
    termos.add(k.t + (c ? ' + ' + c.t : ''));
  }
  return { ok: hits.length > 0, filtros: hits, termos: [...termos] };
}

const cfg = $('Configuração').first().json;
const q = $input.item.json;
const tentativa = (q.tentativa || 0) + 1;
await new Promise(r => setTimeout(r, cfg.pncp.pausaEntrePaginasMs));

let status = 0, body = null, erro = null;
try {
  const r = await this.helpers.httpRequest({
    method: 'GET',
    url: 'https://pncp.gov.br/api/consulta/v1/contratacoes/proposta',
    qs: { dataFinal: cfg.janela.dataFinalPNCP, uf: q.uf, pagina: q.pagina, tamanhoPagina: cfg.tamanhoPagina },
    headers: { Accept: 'application/json' },
    json: true, returnFullResponse: true, ignoreHttpStatusErrors: true, timeout: 90000,
  });
  status = r.statusCode;
  body = r.body;
} catch (e) {
  erro = e.message;
}

if (!(status === 200 || status === 204)) {
  const pode = tentativa < cfg.pncp.esperasSegundos.length + 1;
  return { json: {
    uf: q.uf, pagina: q.pagina, tentativa, status, erro: erro || (typeof body === 'string' ? body.slice(0, 120) : null),
    repetir: pode, espera: cfg.pncp.esperasSegundos[Math.min(tentativa - 1, cfg.pncp.esperasSegundos.length - 1)],
    falhou: !pode, matches: [], lidos: 0, naJanela: 0, totalPaginas: 0,
  } };
}

const dados = (body && body.data) || [];
const comp = compilar(cfg.filtros);
const ufsAlvo = new Set(cfg.ufs);
let naJanela = 0;
const matches = [];
for (const x of dados) {
  const uf = x.unidadeOrgao && x.unidadeOrgao.ufSigla;
  const fim = x.dataEncerramentoProposta || '';
  if (!ufsAlvo.has(uf)) continue;
  if (fim < cfg.janela.inicio || fim > cfg.janela.fim) continue;
  if (cfg.situacoesExcluidas.includes(Number(x.situacaoCompraId))) continue;
  naJanela++;
  const r = avaliar(`${x.objetoCompra || ''} ${x.informacaoComplementar || ''}`, comp);
  if (!r.ok) continue;
  const cnpj = x.orgaoEntidade.cnpj;
  matches.push({
    numeroControlePNCP: x.numeroControlePNCP, uf, municipio: x.unidadeOrgao.municipioNome,
    orgao: x.orgaoEntidade.razaoSocial, unidade: x.unidadeOrgao.nomeUnidade, cnpj,
    anoCompra: x.anoCompra, sequencialCompra: x.sequencialCompra, numeroCompra: x.numeroCompra, processo: x.processo,
    objetoCompra: (x.objetoCompra || '').trim(), informacaoComplementar: x.informacaoComplementar,
    dataAberturaProposta: x.dataAberturaProposta, dataEncerramentoProposta: x.dataEncerramentoProposta,
    modalidadeId: x.modalidadeId, modalidadeNome: x.modalidadeNome, modoDisputaNome: x.modoDisputaNome,
    srp: x.srp, valorTotalEstimado: x.valorTotalEstimado, amparoLegal: x.amparoLegal && x.amparoLegal.nome,
    situacaoCompraNome: x.situacaoCompraNome, usuarioNome: x.usuarioNome, linkSistemaOrigem: x.linkSistemaOrigem || null,
    link_pncp: `https://pncp.gov.br/app/editais/${cnpj}/${x.anoCompra}/${x.sequencialCompra}`,
    termos: r.termos, filtros: r.filtros,
  });
}
return { json: {
  uf: q.uf, pagina: q.pagina, tentativa, status, repetir: false, falhou: false,
  totalPaginas: (body && body.totalPaginas) || 0, lidos: dados.length, naJanela, matches,
} };
