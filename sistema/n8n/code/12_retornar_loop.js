// Fecha a iteração: devolve ao loop apenas o essencial (o "done" do loop acumula estes itens).
const x = $('Aplicar revisão').item.json;
const w = $input.item.json || {};
return {
  json: {
    controle: x.rec.numeroControlePNCP,
    analise: x.analise,
    gravacao: w.error ? 'ERRO: ' + JSON.stringify(w.error).slice(0, 200) : (w.resumo || 'ok'),
    declaracoes_geradas: w.declaracoes || [],
  },
};
