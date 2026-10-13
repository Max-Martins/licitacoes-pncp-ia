// AGENTE 2 — ANALISTA DE EDITAL (Gemini Pro, contexto longo): leitura integral e extração estruturada com citação de fonte.
const cfg = $('Configuração').first().json;
const rec = $('Loop · processos').item.json;
const doc = $input.item.json;

const ESQUEMA = `{
  "resumo": "3-5 linhas: o que é comprado, como, para quem",
  "relevancia": "ALTA|MEDIA|BAIXA|DESCARTAR",
  "justificativa_relevancia": "por que, citando itens",
  "prazos": {
    "validade_proposta": {"valor": "...", "fonte": "arquivo · pág. · cláusula"},
    "validade_produtos": {"valor": "validade mínima exigida na entrega (ex.: 12 meses ou 75% do prazo)", "fonte": "..."},
    "prazo_entrega": {"valor": "prazo após recebimento do empenho/OF/AF", "fonte": "..."},
    "prazo_pagamento": {"valor": "...", "fonte": "..."},
    "vigencia_ata_contrato": {"valor": "...", "fonte": "..."},
    "local_entrega": {"valor": "...", "fonte": "..."}
  },
  "garantias_e_custos": {
    "garantia_proposta": {"valor": "Exigida? %? (art. 58)", "fonte": "..."},
    "garantia_contratual": {"valor": "Exigida? % (art. 96-98)", "fonte": "..."},
    "pagamento_antecipado": {"valor": "taxas, custos de amostra, frete, pagamento antecipado pelo fornecedor", "fonte": "..."},
    "amostras": {"valor": "exige amostra/prova de conceito? prazo e local", "fonte": "..."},
    "visita_tecnica": {"valor": "...", "fonte": "..."},
    "exclusividade_me_epp": {"valor": "exclusivo / cota reservada / ampla", "fonte": "..."}
  },
  "habilitacao": [{"documento": "...", "fonte": "..."}],
  "exigencias_tecnicas": [{"exigencia": "registros (ex.: ANVISA), certificações, laudos, catálogo, amostra, comodato...", "fonte": "..."}],
  "declaracoes": [{"nome": "Declaração de ...", "conteudo": "o que precisa declarar", "momento": "proposta|habilitação|contratação", "obrigatoria": true, "fonte": "arquivo · pág. · cláusula", "fundamento": "artigo/lei citado", "texto_modelo_edital": "transcrição INTEGRAL se o edital trouxer modelo; senão vazio"}],
  "itens_aderentes": [{"item": "nº", "descricao": "resumo", "quantidade": "...", "comentario": "por que é aderente"}],
  "orgao_contato": {"endereco": "endereço completo do órgão (rua, nº, bairro, CEP, cidade/UF)", "telefone": "...", "site": "...", "email": "..."},
  "itens_edital": [{"lote": "nº do lote, se houver", "numero": "nº do item", "descricao": "especificação COMPLETA do TR/edital (não resuma)", "quantidade": 0, "unidade": "UN/CX/FR/KIT...", "valor_unitario_estimado": 0, "marca_referencia": "marca/modelo citado como referência, se houver", "fonte": "arquivo · pág."}],
  "riscos": ["..."],
  "pontos_esclarecimento_impugnacao": ["cláusula restritiva, marca dirigida, prazo inexequível, exigência sem amparo legal..."],
  "lacunas": ["informações que não foram encontradas"]
}`;

const e = cfg.empresa;
const system = `Você é um analista sênior de licitações (Lei 14.133/2021) da empresa fornecedora ${e.nome}.
${[e.cnaePrincipal, e.cnaeSecundario].filter(Boolean).length ? 'CNAEs: ' + [e.cnaePrincipal, e.cnaeSecundario].filter(Boolean).join('; ') + '.' : ''}
Portfólio: ${e.portfolio}

Leia TODOS os documentos (edital, termo de referência, ETP, anexos, minuta de contrato/ata) e extraia as informações abaixo.
REGRAS OBRIGATÓRIAS:
1. Só afirme o que está escrito. Para cada informação, indique a fonte no formato "arquivo · pág. N · cláusula X.Y" usando os marcadores [[arquivo | página N]].
2. Se não encontrar, escreva exatamente "NÃO HÁ INFORMAÇÃO SUFICIENTE" no valor e deixe a fonte vazia.
3. Se edital e TR divergirem, registre AMBOS e aponte a divergência em "riscos".
4. DECLARAÇÕES: varra o documento inteiro — elas costumam estar espalhadas (corpo do edital, habilitação, proposta, TR, anexos, minuta). Liste CADA declaração exigida separadamente, sem fundir duas em uma, inclusive as genéricas (ME/EPP, menor/art. 7º XXXIII CF, inexistência de fato impeditivo, reserva de cargos PcD/reabilitados art. 63 IV, cumprimento de requisitos de habilitação, proposta compatível/exequível, elaboração independente, ciência do edital, vínculo/nepotismo, LGPD etc.). Se houver modelo no edital, transcreva-o integralmente.
5. Não confunda prazo de entrega da proposta com início da disputa.
6. ITENS: em "itens_edital" liste TODOS os itens do TR/edital (até 150), com a especificação técnica completa, quantidade e unidade exatamente como no documento. Eles serão cruzados com o catálogo da empresa.
Responda SOMENTE com JSON válido neste esquema:
${ESQUEMA}`;

const user = `PROCESSO: ${rec.modalidadeNome} nº ${rec.numeroCompra}/${rec.anoCompra} — Processo ${rec.processo}
ÓRGÃO: ${rec.orgao} (${rec.municipio}/${rec.uf})
OBJETO: ${rec.objetoCompra}
ENCERRAMENTO DAS PROPOSTAS: ${rec.dataEncerramentoProposta} | SRP: ${rec.srp ? 'Sim' : 'Não'} | Valor estimado: ${rec.valorTotalEstimado}
ITENS (PNCP): ${JSON.stringify((doc.itens || []).slice(0, 150))}
AVISOS DA COLETA: ${(doc.avisos || []).join(' | ') || 'nenhum'}

===== DOCUMENTOS (texto extraído) =====
${(doc.texto || '').slice(0, cfg.ia.maxCharsAnalista) || '[nenhum texto disponível — analise apenas com os dados do PNCP e registre a lacuna]'}`;

return {
  json: {
    pasta_rel: doc.relativo,
    texto: doc.texto || '',
    body: {
      systemInstruction: { parts: [{ text: system }] },
      contents: [{ role: 'user', parts: [{ text: user }] }],
      generationConfig: { temperature: 0.1, responseMimeType: 'application/json', maxOutputTokens: 32768 },
    },
    modelo: cfg.ia.geminiAnalise,
  },
};
