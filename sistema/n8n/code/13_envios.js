// Monta um envio por destinatário (relatório filtrado pelas UFs de cada um).
const cfg = $('Configuração').first().json;
const payload = $('Montar payload · Relatório').first().json;
return cfg.envios.map(e => {
  const sufixo = e.ufs.join('-');
  const qtd = payload.oportunidades.filter(o => e.ufs.includes(o.uf)).length;
  return { json: { para: e.para, ufs: e.ufs, sufixo, qtdPrevista: qtd, janela: cfg.janela.rotulo,
    payload: { ...payload, ufs_filtro: e.ufs, sufixo } } };
});
