// AGENTE 3 — AUDITOR (Claude): confere a extração do Analista contra o texto, corrige, completa as declarações
// e redige modelos de declaração quando o edital não traz modelo.
function lerGemini(r) {
  if (!r || r.error) throw new Error('Analista falhou: ' + JSON.stringify(r && r.error || r).slice(0, 300));
  const t = r.candidates[0].content.parts.map(p => p.text || '').join('');
  return JSON.parse(t.replace(/^```json\s*|```\s*$/g, ''));
}
const cfg = $('Configuração').first().json;
const rec = $('Loop · processos').item.json;
const prep = $('Montar prompt · Analista').item.json;
let analista = null, erroAnalista = null;
const entrada = $input.item.json || {};
if (entrada.body && entrada.modelo && !entrada.candidates) {
  erroAnalista = 'Analista Gemini desativado (chave gratuita) — extração completa feita pelo Auditor';
} else {
  try { analista = lerGemini(entrada); } catch (e) { erroAnalista = e.message; }
}

const system = `Você é o AUDITOR de uma equipe de análise de editais (Lei 14.133/2021) da empresa fornecedora ${cfg.empresa.nome}. Portfólio: ${cfg.empresa.portfolio}
Outro agente (Analista) extraiu dados do edital. Sua função:
1. Conferir CADA campo contra o texto dos documentos. Corrija valores errados, fontes erradas e preencha o que faltou.
2. Varrer de novo o texto procurando DECLARAÇÕES exigidas que o Analista não listou (procure por "declara", "declaração", "anexo", "modelo", "sob as penas da lei").
3. Para cada declaração SEM modelo no edital, redija em "modelo_sugerido" um texto formal, objetivo, com os campos [RAZÃO SOCIAL], [CNPJ], [ENDEREÇO], [REPRESENTANTE], fiel à exigência do edital.
4. Nunca invente cláusulas. Se não houver base no texto, use "NÃO HÁ INFORMAÇÃO SUFICIENTE".
5. Adicione "auditoria": {"confianca": "ALTA|MEDIA|BAIXA", "divergencias": ["o que você corrigiu e por quê"]}.
Preserve e confira a lista "itens_edital" (todos os itens, especificação completa — não resuma nem corte).
Responda SOMENTE com o JSON completo e corrigido, no MESMO esquema recebido (mais "auditoria" e "modelo_sugerido" nas declarações).`;

const user = `PROCESSO: ${rec.orgao} — ${rec.modalidadeNome} ${rec.numeroCompra}/${rec.anoCompra} — ${rec.objetoCompra}

JSON DO ANALISTA:
${analista ? JSON.stringify(analista) : 'Não há extração prévia (' + erroAnalista + '). Faça a extração completa você mesmo, no esquema: resumo, relevancia, justificativa_relevancia, prazos{validade_proposta, validade_produtos, prazo_entrega, prazo_pagamento, vigencia_ata_contrato, local_entrega}, garantias_e_custos{garantia_proposta, garantia_contratual, pagamento_antecipado, amostras, visita_tecnica, exclusividade_me_epp} (cada um {valor,fonte}), habilitacao[], exigencias_tecnicas[], declaracoes[{nome,conteudo,momento,obrigatoria,fonte,fundamento,texto_modelo_edital}], itens_aderentes[], orgao_contato{endereco,telefone,site,email}, itens_edital[{lote,numero,descricao,quantidade,unidade,valor_unitario_estimado,marca_referencia,fonte}], riscos[], pontos_esclarecimento_impugnacao[], lacunas[]'}

===== DOCUMENTOS =====
${prep.texto.slice(0, cfg.ia.maxCharsAuditor) || '[sem texto]'}`;

return {
  json: {
    analista,
    erroAnalista,
    body: {
      model: cfg.ia.claudeAuditor,
      max_tokens: 32000,
      // sem 'temperature': os modelos Claude atuais rejeitam o parâmetro
      system,
      messages: [{ role: 'user', content: user }],
    },
  },
};
