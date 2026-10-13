// Separa os processos que terão edital baixado e analisado. Nunca devolve lista vazia (o loop precisa rodar
// para que o relatório seja gerado mesmo quando nada for analisado).
const cfg = $('Configuração').first().json;
const ordem = { ALTA: 0, MEDIA: 1, NAO_AVALIADO: 2, BAIXA: 3, DESCARTAR: 4 };
const sel = $input.all().map(i => i.json)
  .filter(p => p.analisar)
  .sort((a, b) => (ordem[a.relevancia_triagem] ?? 9) - (ordem[b.relevancia_triagem] ?? 9))
  .slice(0, cfg.ia.limiteProcessosAnalise);
if (!sel.length) return [{ json: { sentinela: true } }];
return sel.map(j => ({ json: j }));
