// Consolida: usa a versão auditada (Claude); se o auditor falhar, mantém a do Analista (Gemini) e registra.
// Se o nó "Agente Revisor · ChatGPT" estiver ativo, a resposta dele chega aqui e é anexada como segunda opinião.
function extrairJSON(txt) {
  const limpo = String(txt || '').replace(/^```json\s*|```\s*$/g, '').trim();
  const i = limpo.indexOf('{');
  const j = limpo.lastIndexOf('}');
  return JSON.parse(limpo.slice(i, j + 1));
}
const rec = $('Loop · processos').item.json;
const prep = $('Montar prompt · Auditor').item.json;
const r = $input.item.json || {};
let final = null;
const avisos = [];

// Resposta do Claude (Messages API) — ou do ChatGPT (Chat Completions) se o revisor estiver ligado
try {
  if (r.error) throw new Error(JSON.stringify(r.error).slice(0, 200));
  if (Array.isArray(r.content)) final = extrairJSON(r.content.filter(c => c.type === 'text').map(c => c.text).join(''));
  else if (r.choices) final = extrairJSON(r.choices[0].message.content);
  else throw new Error('resposta sem conteúdo');
} catch (e) {
  avisos.push('Auditor indisponível: ' + e.message);
}
if (!final && prep.analista) {
  final = prep.analista;
  avisos.push('Análise SEM auditoria cruzada — conferir manualmente.');
}
if (!final) {
  final = { resumo: 'Análise automática falhou: ' + (prep.erroAnalista || ''), relevancia: rec.relevancia_triagem, declaracoes: [], lacunas: ['Analisar manualmente'] };
}
final.auditoria = final.auditoria || {};
final.auditoria.avisos = [...(final.auditoria.avisos || []), ...avisos];
final.relevancia = final.relevancia || rec.relevancia_triagem;

return { json: { pasta_rel: $('Montar prompt · Analista').item.json.pasta_rel, rec, analise: final } };
