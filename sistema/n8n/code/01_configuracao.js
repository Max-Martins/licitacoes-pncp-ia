// ===================== CONFIGURAÇÃO GERAL =====================
// Edite apenas este bloco. Todo o restante do fluxo lê daqui.
const CONFIG = {
  ufs: ['SP', 'MG', 'PR', 'GO', 'SC', 'MS'], // UFs pesquisadas no PNCP (qualquer uma das 27)
  diasAteInicio: 3,          // execução em 11/10 -> janela começa em 14/10 (o dia da execução não conta)
  diasJanela: 15,            // 14/10 a 28/10 (15 dias corridos)
  diasAgendados: [1, 16],    // dias do mês do agendamento (nó "Dias 1 e 16 · 07:00")
  dataExecucao: null,        // null = hoje. Para reprocessar: '2026-10-11'
  tamanhoPagina: 50,          // máximo aceito pelo PNCP
  pncp: {
    pausaEntrePaginasMs: 1500, // ritmo que o PNCP tolera sem bloquear o IP
    esperasSegundos: [15, 30, 60, 60, 90, 120, 180, 300], // espera progressiva após HTTP 429/5xx
  },
  // Envio do relatório: um arquivo por destinatário, só com as UFs dele. Separe vários e-mails por vírgula.
  remetente: 'Seu Nome <seu-email@exemplo.com.br>',  // precisa ser a mesma conta da credencial SMTP
  assinatura: 'Seu Nome<br>Analista de Licitações · Sua Empresa',
  envios: [
    { para: 'licitacao@exemplo.com.br', ufs: ['SP', 'MG', 'PR', 'GO', 'SC', 'MS'] },
    // { para: 'vendas-sp@exemplo.com.br', ufs: ['SP'] },
  ],
  workerUrl: 'http://licitacoes-worker:8765', // worker da mesma pilha Docker (n8n fora do Docker: http://localhost:8765)
  // Dados da sua empresa: entram na proposta prévia e nas declarações. Campo vazio sai destacado em amarelo.
  empresa: {
    nome: 'Sua Empresa',
    razao_social: 'SUA EMPRESA LTDA',
    nome_fantasia: '',
    cnpj: '',
    ie: '',
    im: '',
    endereco: '',
    bairro: '',
    municipio_uf: '',
    cep: '',
    cidade_assinatura: '',
    telefone: '',
    email: '',
    vendedor: '',
    rubrica: '',
    representante: { nome: '', rg: '', cpf: '', cargo: '', estado_civil: '', emails: '' },
    // Usados na proposta quando o edital não define (saem destacados em amarelo para conferência)
    padroes: { validade_proposta: '60 (sessenta) dias', condicao_pagamento: '30 dias', prazo_entrega: '20 dias' },
    cnaePrincipal: '46.45-1-01 — Comércio atacadista de instrumentos e materiais para uso médico, cirúrgico, hospitalar e de laboratórios',
    cnaeSecundario: '',
    // Descreva o que a empresa vende: a IA usa este texto para decidir o que é oportunidade.
    portfolio: 'Reagentes e kits para diagnóstico in vitro (bioquímica, hematologia, coagulação, imunologia, microbiologia, testes rápidos), meios de cultura, tubos de coleta de sangue a vácuo, plásticos e vidrarias de laboratório, consumíveis e pequenos equipamentos laboratoriais.',
    // Regras da triagem por IA (ALTA / MEDIA / BAIXA / DESCARTAR). Ajuste ao seu ramo.
    criteriosTriagem: `- ALTA: objeto é essencialmente reagentes, insumos, materiais ou equipamentos de laboratório ou diagnóstico.
- MEDIA: objeto amplo (material médico-hospitalar, insumos de saúde) que provavelmente contém itens do portfólio.
- BAIXA: aderência remota, poucos itens possíveis.
- DESCARTAR: claramente fora do portfólio (obras, serviços, alimentos, veículos, medicamentos etc.): falso positivo do filtro por palavra-chave.
Atenção: "exames laboratoriais" como SERVIÇO terceirizado é DESCARTAR, salvo se houver comodato ou fornecimento de reagentes.`,
  },
  ia: {
    // Modelos configuráveis (os nomes mudam com o tempo — confira no painel de cada provedor)
    // Aliases "-latest" acompanham o modelo atual do Google (não quebram quando uma versão é aposentada).
    // Chave gratuita: Pro tem cota ZERO -> usar Flash. Com faturamento ativo no AI Studio: geminiAnalise = 'gemini-pro-latest'.
    geminiTriagem: 'gemini-flash-latest',
    geminiAnalise: 'gemini-flash-latest', // usado só se o nó "Agente Analista · Gemini" for reativado (exige faturamento)
    claudeAuditor: 'claude-sonnet-5-5',  // confira o nome atual em docs.claude.com
    openaiRevisor: 'gpt-5',
    maxCharsAnalista: 600000,   // ~150 mil tokens
    maxCharsAuditor: 350000,    // ~90 mil tokens
    analisarDescartados: false, // true = baixa e analisa até o que a triagem marcou como DESCARTAR
    // Economia: análise completa (Claude + ChatGPT + cruzamento) só para estas classificações da triagem.
    // BAIXA continua no relatório, mas sem análise de edital. Para incluir: ['ALTA', 'MEDIA', 'BAIXA', 'NAO_AVALIADO']
    analisarRelevancias: ['ALTA', 'MEDIA', 'NAO_AVALIADO'],
    triagemLote: 30,            // processos por chamada de triagem (chave gratuita do Gemini: 20 chamadas/dia por modelo)
    limiteProcessosAnalise: 200,
  },
  // Filtros por palavra-chave (sistema/filtros.json): chave + complementares (opcional) + exclusões
  filtros: /*__FILTROS__*/,
  // Situações do PNCP que NÃO são oportunidade (2 revogada, 3 anulada, 4 suspensa)
  situacoesExcluidas: [2, 3, 4],
};

// ===================== JANELA DE DATAS =====================
const TZ = 'America/Sao_Paulo';
const hojeISO = CONFIG.dataExecucao ||
  new Intl.DateTimeFormat('en-CA', { timeZone: TZ, year: 'numeric', month: '2-digit', day: '2-digit' }).format(new Date());
const base = new Date(hojeISO + 'T00:00:00Z');
const addDias = (d, n) => new Date(d.getTime() + n * 86400000);
const ymd = d => d.toISOString().slice(0, 10);
const ini = addDias(base, CONFIG.diasAteInicio);
let fim = addDias(ini, CONFIG.diasJanela - 1);
// Agendamento em dias fixos (1 e 16): a janela vai até a véspera do início da próxima execução,
// para não deixar buraco nos meses de 31 dias nem repetir datas. Execução manual em outro dia: 15 dias.
const diaHoje = base.getUTCDate();
if ((CONFIG.diasAgendados || []).includes(diaHoje)) {
  const dias = [...CONFIG.diasAgendados].sort((a, b) => a - b);
  const seguinte = dias.find(d => d > diaHoje);
  const proxima = seguinte
    ? new Date(Date.UTC(base.getUTCFullYear(), base.getUTCMonth(), seguinte))
    : new Date(Date.UTC(base.getUTCFullYear(), base.getUTCMonth() + 1, dias[0]));
  fim = addDias(proxima, CONFIG.diasAteInicio - 1);
}
const br = d => ymd(d).split('-').reverse().join('/');

return [{
  json: {
    ...CONFIG,
    execucao: hojeISO,
    janela: {
      inicio: ymd(ini) + 'T00:00:00',
      fim: ymd(fim) + 'T23:59:59',
      dataFinalPNCP: ymd(fim).replace(/-/g, ''),
      rotulo: `${br(ini)} a ${br(fim)}`,
    },
  },
}];
