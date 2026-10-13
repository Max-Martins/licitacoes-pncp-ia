// Junta as respostas dos lotes da triagem. Lote que falhar NÃO descarta nada (fail-open): seus processos seguem
// para análise como NAO_AVALIADO e o aviso vai para o relatório.
const itens = $('Consolidar + Filtros').all().map(i => i.json).filter(j => !j.vazio);
const cfg = $('Configuração').first().json;
const mapa = {};
const falhas = [];
const respostas = $input.all().map(i => i.json || {});
respostas.forEach((resp, n) => {
  try {
    if (resp.error) throw new Error(JSON.stringify(resp.error).slice(0, 160));
    const txt = resp.candidates[0].content.parts.map(p => p.text || '').join('');
    const dados = JSON.parse(txt.replace(/^```json\s*|```$/g, ''));
    for (const r of dados.resultados || []) mapa[r.id] = r;
  } catch (e) {
    falhas.push(`lote ${n + 1}: ${e.message}`);
  }
});
const aviso = falhas.length
  ? `Triagem por IA incompleta (${falhas.length} de ${respostas.length} lote(s) falharam) — os processos desses lotes seguem para análise sem classificação. ${falhas[0]}`
  : null;
const niveis = (cfg.ia && cfg.ia.analisarRelevancias) || ['ALTA', 'MEDIA', 'NAO_AVALIADO'];
return itens.map((p, i) => {
  const t = mapa[i];
  const relevancia = t ? String(t.relevancia).toUpperCase().replace('MÉDIA', 'MEDIA') : 'NAO_AVALIADO';
  return {
    json: {
      ...p,
      relevancia_triagem: relevancia,
      motivo_triagem: t ? t.motivo : null,
      aviso_triagem: aviso,
      analisar: cfg.ia.analisarDescartados || niveis.includes(relevancia),
    },
  };
});
