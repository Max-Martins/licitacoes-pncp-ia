// AGENTE 1 — TRIAGEM (Gemini Flash, chave gratuita): classifica a aderência dos processos EM LOTES.
// A chave gratuita permite ~20 chamadas/dia por modelo: lotes de 30 processos = ~6 chamadas por execução.
const cfg = $('Configuração').first().json;
const itens = $input.all().map(i => i.json).filter(j => !j.vazio);
const TAM = (cfg.ia && cfg.ia.triagemLote) || 30;

const e = cfg.empresa;
const system = `Você é analista sênior de licitações públicas (Lei 14.133/2021) de uma empresa fornecedora.
Empresa: ${e.nome}.${e.cnaePrincipal ? ` CNAE principal ${e.cnaePrincipal}.` : ''}${e.cnaeSecundario ? ` CNAE secundário ${e.cnaeSecundario}.` : ''}
Portfólio: ${e.portfolio}
Tarefa: para cada processo, decidir se vale a pena a empresa analisar o edital.
Critérios:
${e.criteriosTriagem}
Use exatamente o "id" recebido. Responda SOMENTE JSON: {"resultados":[{"id":0,"relevancia":"ALTA|MEDIA|BAIXA|DESCARTAR","motivo":"até 25 palavras"}]}`;

const lotes = [];
for (let ini = 0; ini < itens.length; ini += TAM) {
  const lista = itens.slice(ini, ini + TAM).map((p, k) => ({
    id: ini + k, // id global: permite juntar os lotes depois
    orgao: p.orgao,
    modalidade: p.modalidadeNome,
    objeto: (p.objetoCompra || '').slice(0, 900),
    complemento: (p.informacaoComplementar || '').slice(0, 300),
    termos_encontrados: p.termos,
  }));
  lotes.push({
    json: {
      lote: lotes.length + 1, ids: [ini, ini + lista.length - 1], qtd: lista.length,
      body: {
        systemInstruction: { parts: [{ text: system }] },
        contents: [{ role: 'user', parts: [{ text: JSON.stringify(lista) }] }],
        generationConfig: { temperature: 0, responseMimeType: 'application/json', maxOutputTokens: 16384 },
      },
      modelo: cfg.ia.geminiTriagem,
    },
  });
}
return lotes.length ? lotes : [{ json: { lote: 0, qtd: 0, vazio: true, body: {}, modelo: cfg.ia.geminiTriagem } }];
