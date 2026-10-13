// Motor de palavras-chave (sistema/filtros.json) — usado no n8n (Code node) e nos testes.
// Regras: sem acento/maiúsculas; termo casa no INÍCIO de palavra (prefixo);
// termos com várias palavras aceitam até 2 conectivos curtos entre elas ("meio de cultura").
function normalizar(txt) {
  return String(txt || '')
    .normalize('NFD').replace(/[̀-ͯ]/g, '')
    .toLowerCase()
    .replace(/[^a-z0-9\-\/ ]+/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
}

function termoParaRegex(termo, exato) {
  const partes = normalizar(termo).split(' ').filter(Boolean)
    .map(p => p.replace(/[.*+?^${}()|[\]\\\/-]/g, '\\$&'));
  if (!partes.length) return null;
  const meio = partes.join('(?:\\s+[a-z]{1,4}){0,2}\\s+');
  return new RegExp('(?:^|[^a-z0-9])' + meio + (exato ? '(?![a-z0-9])' : ''), 'i');
}

function compilarFiltros(filtros) {
  const c = (r, ex) => (r || []).map(t => ({ t, re: termoParaRegex(t, ex) })).filter(x => x.re);
  return filtros.map(f => ({
    id: f.id, chave: c(f.chave, f.exato), comp: c(f.complementares), excl: c(f.exclusoes),
  }));
}

// Retorna {ok, filtros:[ids], termos:[...]} para um texto
function avaliar(texto, compilados) {
  const n = ' ' + normalizar(texto) + ' ';
  const hits = [];
  const termos = new Set();
  for (const f of compilados) {
    const k = f.chave.find(x => x.re.test(n));
    if (!k) continue;
    let comp = null;
    if (f.comp.length) { comp = f.comp.find(x => x.re.test(n)); if (!comp) continue; }
    if (f.excl.some(x => x.re.test(n))) continue;
    hits.push(f.id);
    termos.add(k.t + (comp ? ' + ' + comp.t : ''));
  }
  return { ok: hits.length > 0, filtros: hits, termos: [...termos] };
}

if (typeof module !== 'undefined') module.exports = { normalizar, termoParaRegex, compilarFiltros, avaliar };
