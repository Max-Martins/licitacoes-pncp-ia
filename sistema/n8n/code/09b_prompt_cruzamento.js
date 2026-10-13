// AGENTE 5 — CRUZAMENTO (Claude): compara cada item do edital com os candidatos pré-selecionados
// nas tabelas de preço da empresa (uma por planilha em _CATALOGOS) e escolhe o produto que atende (com o nosso código).
const cfg = $('Configuração').first().json;
const base = $('Aplicar revisão').item.json;
const cand = $input.item.json || {};
const itens = (cand.itens || []).filter(i => Object.values(i.candidatos || {}).some(l => (l || []).length));

const compacto = itens.map(i => ({
  numero: i.numero, descricao: i.descricao, quantidade: i.quantidade, unidade: i.unidade,
  valor_unitario_estimado: i.valor_unitario_estimado, marca_referencia: i.marca_referencia || undefined,
  candidatos: Object.fromEntries(Object.entries(i.candidatos || {}).map(([emp, l]) => [emp,
    (l || []).map(c => ({ codigo: c.codigo, descricao: c.descricao, marca: c.marca, preco_tabela: c.preco }))])),
}));

const tabelas = Object.entries(cand.catalogos || {}).map(([id, c]) => `${id} (${(c && c.nome) || id})`);
const ids = Object.keys(cand.catalogos || {});
const exemplo = ids.length ? ids : ['TABELA'];
const system = `Você é especialista técnico em produtos e analista de licitações (Lei 14.133/2021) da empresa ${cfg.empresa.nome}.
Portfólio: ${cfg.empresa.portfolio}
Para cada item do edital, compare a especificação com os produtos CANDIDATOS de cada tabela de preço: ${tabelas.join(', ') || 'nenhuma'}.
REGRAS:
1. Escolha SOMENTE entre os candidatos fornecidos (use o "codigo" exatamente como veio). Nunca invente produto ou código.
2. Veredito por tabela:
   - ATENDE: todas as características obrigatórias batem (material, volume/tamanho, composição, método, apresentação, nº de testes etc.).
   - ATENDE_PARCIAL: mesmo produto, mas há divergência que precisa de conferência (ex.: embalagem diferente, medida próxima, especificação não informada na tabela).
   - NAO_ATENDE: nenhum candidato atende. Nesse caso "codigo": null.
3. Seja rigoroso: medida, volume, composição e método errados = NAO_ATENDE. Na dúvida, ATENDE_PARCIAL com a divergência explicada.
4. Embalagem: se a tabela vende em caixa/pacote (ex.: "C/100", "COM 1000UN", "10UN") e o edital pede por unidade, informe "itens_por_embalagem" (número) e "converter_para_unidade": true. Se a unidade do edital já for a embalagem (CX, PCT, KIT), "converter_para_unidade": false.
5. Se o edital cita marca de referência, diga se o ofertado é a mesma marca ou similar.
6. A proposta é emitida pela ${cfg.empresa.nome} e pode ofertar produtos de qualquer tabela.
   Em "escolha" indique de qual tabela sai o produto a ofertar: primeiro o que melhor atende; empate técnico, o de menor preço. Se nenhum atende, null.
7. Seja objetivo: justificativa em 1 frase; divergências em itens curtos.
Responda SOMENTE JSON:
{"itens":[{"numero":"1",${exemplo.map(t => `"${t}":{"codigo":"123"|null,"veredito":"ATENDE|ATENDE_PARCIAL|NAO_ATENDE","justificativa":"...","divergencias":["..."],"itens_por_embalagem":1,"converter_para_unidade":false}`).join(',')},"escolha":${exemplo.map(t => `"${t}"`).join('|')}|null,"recomendacao":"produto a ofertar e por quê (1 frase)"}],"observacoes_gerais":["..."]}`;

const user = `PROCESSO: ${base.rec.orgao} — ${base.rec.modalidadeNome} ${base.rec.numeroCompra}/${base.rec.anoCompra} — ${base.rec.objetoCompra}
ITENS COM CANDIDATOS (${compacto.length}):
${JSON.stringify(compacto)}`;

return {
  json: {
    ...base,
    cruzamento_entrada: { catalogos: cand.catalogos || {}, itens: cand.itens || [], total_itens: cand.total_itens || 0, erro: cand.error ? JSON.stringify(cand.error).slice(0, 200) : null },
    tem_itens: compacto.length > 0,
    body: {
      model: cfg.ia.claudeAuditor,
      max_tokens: 32000,
      system,
      messages: [{ role: 'user', content: user }],
    },
  },
};
