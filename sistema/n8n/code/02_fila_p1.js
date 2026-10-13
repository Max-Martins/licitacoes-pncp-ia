// Fila inicial: página 1 de cada UF (descobre quantas páginas existem).
const cfg = $('Configuração').first().json;
return cfg.ufs.map(uf => ({ json: { uf, pagina: 1, tentativa: 0 } }));
