// Com as páginas 1 em mãos, gera a fila das páginas 2..N de cada UF.
// O resultado das páginas 1 viaja no primeiro item (p1) para a consolidação.
const p1 = $input.all().map(i => i.json);
const fila = [];
for (const r of p1) {
  for (let p = 2; p <= (r.totalPaginas || 0); p++) fila.push({ uf: r.uf, pagina: p, tentativa: 0 });
}
if (!fila.length) fila.push({ sentinela: true });
fila[0].p1 = p1;
return fila.map(j => ({ json: j }));
