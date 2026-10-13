// Junta os resultados de todas as páginas (página 1 + demais), remove duplicidades e gera estatísticas.
const p1 = $('Fila · demais páginas').first().json.p1 || [];
const demais = $input.all().map(i => i.json).filter(j => !j.sentinela);
const paginas = [...p1, ...demais];

const vistos = new Map();
let lidos = 0, naJanela = 0;
const falhas = [];
for (const pg of paginas) {
  if (pg.falhou) { falhas.push(`${pg.uf} p.${pg.pagina} (HTTP ${pg.status}${pg.erro ? ' · ' + pg.erro : ''})`); continue; }
  lidos += pg.lidos || 0;
  naJanela += pg.naJanela || 0;
  for (const m of pg.matches || []) if (!vistos.has(m.numeroControlePNCP)) vistos.set(m.numeroControlePNCP, m);
}
const selecionados = [...vistos.values()].sort((a, b) => a.dataEncerramentoProposta.localeCompare(b.dataEncerramentoProposta));
const estatisticas = {
  paginasConsultadas: paginas.length, registrosLidos: lidos, naJanela,
  selecionados: selecionados.length, paginasComErro: falhas.length, errosAmostra: falhas.slice(0, 8),
};
if (!selecionados.length) return [{ json: { vazio: true, estatisticas } }];
return selecionados.map(s => ({ json: { ...s, estatisticas } }));
