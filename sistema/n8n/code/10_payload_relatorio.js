// Reúne todos os processos selecionados + as análises (saída "done" do loop) e monta o payload do relatório.
const cfg = $('Configuração').first().json;
const consolid = $('Consolidar + Filtros').first().json;
const estat = consolid.estatisticas || {};

let base = [];
if (!consolid.vazio) {
  try { base = $('Aplicar triagem').all().map(i => i.json); } catch (e) { base = []; }
}
const analises = {};
for (const i of $input.all()) {
  if (i.json && i.json.controle && i.json.analise) analises[i.json.controle] = i.json.analise;
}

const oportunidades = base.map(p => ({
  ...p,
  analise: analises[p.numeroControlePNCP] ||
    { relevancia: p.relevancia_triagem, resumo: p.motivo_triagem ? 'Triagem: ' + p.motivo_triagem : null },
}));

const avisos = [];
if (estat.paginasComErro) avisos.push(`${estat.paginasComErro} página(s) do PNCP falharam após as tentativas — resultado pode estar incompleto. ${(estat.errosAmostra || []).join(' | ')}`);
const avisoTriagem = base.find(p => p.aviso_triagem);
if (avisoTriagem) avisos.push(avisoTriagem.aviso_triagem);
const naoAnalisados = base.filter(p => !analises[p.numeroControlePNCP]).length;
if (naoAnalisados) avisos.push(`${naoAnalisados} processo(s) sem análise de edital (descartados na triagem ou acima do limite).`);

return [{
  json: {
    janela_ini: cfg.janela.inicio,
    janela_fim: cfg.janela.fim,
    ufs: cfg.ufs,
    registros_lidos: estat.registrosLidos || null,
    registros_janela: estat.naJanela || null,
    cnpj: cfg.empresa.cnpj || null,
    empresa: cfg.empresa.nome || null,
    cnae: cfg.empresa.cnaePrincipal || null,
    avisos: avisos.join(' · ') || null,
    oportunidades,
  },
}];
