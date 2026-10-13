"""Gera o workflow n8n (JSON importável) a partir dos scripts em ./code — mantém o código versionável e testável."""
import json
import uuid
from pathlib import Path

AQUI = Path(__file__).parent
CODE = AQUI / "code"
MATCHER = (AQUI.parent / "lib" / "matcher.js").read_text(encoding="utf-8").replace(
    "if (typeof module !== 'undefined') module.exports = { normalizar, termoParaRegex, compilarFiltros, avaliar };", "")
FILTROS = json.loads((AQUI.parent / "filtros.json").read_text(encoding="utf-8"))["filtros"]
FILTROS = [{k: v for k, v in f.items() if not k.startswith("_") and k != "ambiguo"} for f in FILTROS]


def js(nome):
    t = (CODE / nome).read_text(encoding="utf-8")
    return t.replace("/*__MATCHER__*/", MATCHER).replace("/*__FILTROS__*/", json.dumps(FILTROS, ensure_ascii=False))


nodes, conns = [], {}


def uid(*partes):
    """Identificador estável: o JSON gerado só muda quando o fluxo muda."""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, "licitacoes-pncp-ia/" + "/".join(partes)))


def node(nome, tipo, versao, params, pos, **extra):
    n = {"parameters": params, "id": uid(nome), "name": nome, "type": tipo, "typeVersion": versao, "position": pos}
    n.update(extra)
    nodes.append(n)
    return nome


def code(nome, arquivo, pos, por_item=False, **extra):
    p = {"jsCode": js(arquivo)}
    if por_item:
        p["mode"] = "runOnceForEachItem"
    return node(nome, "n8n-nodes-base.code", 2, p, pos, **extra)


def liga(origem, destino, saida=0, entrada=0):
    conns.setdefault(origem, {"main": []})
    while len(conns[origem]["main"]) <= saida:
        conns[origem]["main"].append([])
    conns[origem]["main"][saida].append({"node": destino, "type": "main", "index": entrada})


RETRY = {"retryOnFail": True, "maxTries": 5, "waitBetweenTries": 5000}
CONTINUA = {"onError": "continueRegularOutput"}
WORKER = "={{ $('Configuração').first().json.workerUrl }}"


def http_get_pncp(nome, pos, intervalo):
    return node(nome, "n8n-nodes-base.httpRequest", 4.2, {
        "url": "https://pncp.gov.br/api/consulta/v1/contratacoes/proposta",
        "sendQuery": True,
        "queryParameters": {"parameters": [
            {"name": "dataFinal", "value": "={{ $json.dataFinal }}"},
            {"name": "uf", "value": "={{ $json.uf }}"},
            {"name": "pagina", "value": "={{ $json.pagina }}"},
            {"name": "tamanhoPagina", "value": "={{ $json.tamanhoPagina }}"},
        ]},
        "sendHeaders": True,
        "headerParameters": {"parameters": [{"name": "Accept", "value": "application/json"}]},
        "options": {"batching": {"batch": {"batchSize": 1, "batchInterval": intervalo}}, "timeout": 60000},
    }, pos, **RETRY, **CONTINUA, alwaysOutputData=True)


def http_post(nome, url, corpo, pos, timeout=120000, auth=None, headers=None, retry=True):
    p = {"method": "POST", "url": url, "sendBody": True, "specifyBody": "json", "jsonBody": corpo,
         "options": {"timeout": timeout}}
    if headers:
        p["sendHeaders"] = True
        p["headerParameters"] = {"parameters": [{"name": k, "value": v} for k, v in headers.items()]}
    if auth:
        p["authentication"] = "genericCredentialType"
        p["genericAuthType"] = "httpHeaderAuth"
    extra = {**CONTINUA}
    if retry:
        extra.update(RETRY)
    return node(nome, "n8n-nodes-base.httpRequest", 4.2, p, pos, **extra)


def se(nome, expressao, pos):
    return node(nome, "n8n-nodes-base.if", 2, {
        "conditions": {
            "options": {"caseSensitive": True, "leftValue": "", "typeValidation": "loose"},
            "conditions": [{"id": uid(nome, "condicao"), "leftValue": expressao, "rightValue": "",
                            "operator": {"type": "boolean", "operation": "true", "singleValue": True}}],
            "combinator": "and"},
        "options": {}}, pos)


def nota(texto, pos, w, h, cor=None):
    p = {"content": texto, "height": h, "width": w}
    if cor:
        p["color"] = cor
    node(f"Nota {len(nodes)}", "n8n-nodes-base.stickyNote", 1, p, pos)


# ------------------------------------------------------------------ captação (com controle de taxa)
node("Executar manualmente", "n8n-nodes-base.manualTrigger", 1, {}, [-200, 200])
node("Dias 1 e 16 · 07:00", "n8n-nodes-base.scheduleTrigger", 1.2,
     {"rule": {"interval": [{"field": "cronExpression", "expression": "0 7 1,16 * *"}]}}, [-200, 400])
code("Configuração", "01_configuracao.js", [40, 300])
code("Fila · página 1", "02_fila_p1.js", [260, 300])
node("Loop · página 1", "n8n-nodes-base.splitInBatches", 3, {"options": {}}, [480, 300])
code("PNCP · consultar página 1", "03_consultar_pncp.js", [700, 400], por_item=True)
se("Repetir? (p1)", "={{ $json.repetir }}", [920, 400])
node("Aguardar (p1)", "n8n-nodes-base.wait", 1.1, {"resume": "timeInterval", "amount": "={{ $json.espera }}", "unit": "seconds"},
     [1140, 520], webhookId=uid("Aguardar (p1)", "webhook"))
code("Fila · demais páginas", "04_fila_demais.js", [700, 120])
node("Loop · demais páginas", "n8n-nodes-base.splitInBatches", 3, {"options": {}}, [920, 120])
code("PNCP · consultar demais páginas", "03_consultar_pncp.js", [1140, 220], por_item=True)
se("Repetir? (demais)", "={{ $json.repetir }}", [1360, 220])
node("Aguardar (demais)", "n8n-nodes-base.wait", 1.1, {"resume": "timeInterval", "amount": "={{ $json.espera }}", "unit": "seconds"},
     [1580, 340], webhookId=uid("Aguardar (demais)", "webhook"))
se("É sentinela? (demais)", "={{ !!$json.sentinela }}", [1140, 40])
code("Consolidar + Filtros", "04_consolidar_filtrar.js", [1360, -160])
se("Há oportunidades?", "={{ !$json.vazio }}", [1580, -160])

# ------------------------------------------------------------------ triagem
code("Montar prompt · Triagem", "05_prompt_triagem.js", [1800, -160])
http_post("Agente Triagem · Gemini",
          "=https://generativelanguage.googleapis.com/v1beta/models/{{ $json.modelo }}:generateContent",
          "={{ JSON.stringify($json.body) }}", [2020, -160], timeout=300000, auth=True)
# um lote por requisição, com intervalo — a chave gratuita do Gemini não aceita rajadas
nodes[-1]["parameters"]["options"]["batching"] = {"batch": {"batchSize": 1, "batchInterval": 10000}}
code("Aplicar triagem", "06_aplicar_triagem.js", [2240, -160])
code("Selecionar para análise", "06b_selecionar_analise.js", [2460, -160])

# ------------------------------------------------------------------ loop por processo
node("Loop · processos", "n8n-nodes-base.splitInBatches", 3, {"options": {}}, [2680, -160])
se("É item real?", "={{ !$json.sentinela }}", [2900, -60])
http_post("Worker · pastas + downloads", WORKER + "/processo/preparar",
          "={{ JSON.stringify({ rec: $json, max_chars: $('Configuração').first().json.ia.maxCharsAnalista }) }}",
          [3120, -60], timeout=900000)
code("Montar prompt · Analista", "07_prompt_analista.js", [3340, -60], por_item=True)
http_post("Agente Analista · Gemini",
          "=https://generativelanguage.googleapis.com/v1beta/models/{{ $json.modelo }}:generateContent",
          "={{ JSON.stringify($json.body) }}", [3560, -60], timeout=600000, auth=True)
# Chave gratuita do Gemini = 20 chamadas/dia por modelo: o Analista fica desligado e o Auditor (Claude) faz a extração.
# Com faturamento ativo no Google AI Studio, basta reativar este nó.
nodes[-1]["disabled"] = True
nodes[-1]["notes"] = "DESATIVADO: chave gratuita do Gemini (20 chamadas/dia). O Auditor (Claude) faz a extração completa. Reative se ativar o faturamento."
code("Montar prompt · Auditor", "08_prompt_auditor.js", [3780, -60], por_item=True)
http_post("Agente Auditor · Claude", "https://api.anthropic.com/v1/messages",
          "={{ JSON.stringify($json.body) }}", [4000, -60], timeout=600000, auth=True,
          headers={"anthropic-version": "2023-06-01"})
code("Consolidar análise", "09_consolidar_analise.js", [4220, -60], por_item=True)
REVISOR_BODY = ("={{ JSON.stringify({ model: $('Configuração').first().json.ia.openaiRevisor, "
                "response_format: { type: 'json_object' }, messages: [ { role: 'system', content: "
                "'Você é revisor independente de análises de editais (Lei 14.133/2021). Receberá o JSON de análise feito por outros dois agentes. "
                "Verifique coerência, riscos não apontados e declarações que normalmente são exigidas e não foram listadas. "
                "Responda SOMENTE JSON: {\"concorda\": true|false, \"observacoes\": [\"...\"], \"declaracoes_faltantes\": [{\"nome\":\"...\",\"conteudo\":\"...\",\"momento\":\"...\",\"fonte\":\"verificar no edital\"}]}' }, "
                "{ role: 'user', content: JSON.stringify({ processo: $json.rec.objetoCompra, orgao: $json.rec.orgao, analise: $json.analise }) } ] }) }}")
http_post("Agente Revisor · ChatGPT (opcional)", "https://api.openai.com/v1/chat/completions",
          REVISOR_BODY, [4440, -60], timeout=300000, auth=True)
nodes[-1]["disabled"] = True
code("Aplicar revisão", "11_aplicar_revisao.js", [4660, -60], por_item=True)
# cruzamento item do edital × tabelas de preço da empresa -> proposta prévia
http_post("Worker · candidatos do catálogo", WORKER + "/processo/candidatos",
          "={{ JSON.stringify({ itens_pncp: $('Worker · pastas + downloads').item.json.itens || [], "
          "itens_edital: ($json.analise.itens_edital && $json.analise.itens_edital.length) ? $json.analise.itens_edital "
          ": (($('Montar prompt · Auditor').item.json.analista || {}).itens_edital || []), k: 5 }) }}",
          [4880, 160], timeout=120000)
code("Montar prompt · Cruzamento", "09b_prompt_cruzamento.js", [5100, 160], por_item=True)
se("Há itens p/ cruzamento?", "={{ $json.tem_itens }}", [5320, 160])
http_post("Agente Cruzamento · Claude", "https://api.anthropic.com/v1/messages",
          "={{ JSON.stringify($json.body) }}", [5540, 80], timeout=600000, auth=True,
          headers={"anthropic-version": "2023-06-01"})
nodes[-1]["maxTries"] = 3
code("Aplicar cruzamento", "09c_aplicar_cruzamento.js", [5760, 160], por_item=True)
http_post("Worker · gravar análise e declarações", WORKER + "/processo/analise",
          "={{ JSON.stringify({ pasta_rel: $json.pasta_rel, rec: $json.rec, analise: $json.analise, "
          "empresa: $('Configuração').first().json.empresa }) }}",
          [5980, 160], timeout=180000)
code("Retornar ao loop", "12_retornar_loop.js", [6200, 160], por_item=True)

# ------------------------------------------------------------------ relatório
code("Montar payload · Relatório", "10_payload_relatorio.js", [2900, -440])
http_post("Worker · gerar relatório Excel", WORKER + "/relatorio", "={{ JSON.stringify($json) }}", [3120, -440], timeout=300000)
node("Resumo da execução", "n8n-nodes-base.code", 2, {"jsCode": """const r = $input.first().json;
const c = $('Configuração').first().json;
return [{ json: {
  janela: c.janela.rotulo,
  relatorio: r.arquivo || null,
  oportunidades: r.qtd ?? null,
  erro: r.error ? JSON.stringify(r.error).slice(0, 300) : null,
} }];"""}, [3340, -440])

# ------------------------------------------------------------------ conexões
liga("Executar manualmente", "Configuração")
liga("Dias 1 e 16 · 07:00", "Configuração")
liga("Loop · página 1", "Fila · demais páginas", 0)
liga("Loop · página 1", "PNCP · consultar página 1", 1)
liga("Repetir? (p1)", "Aguardar (p1)", 0)
liga("Repetir? (p1)", "Loop · página 1", 1)
liga("Loop · demais páginas", "Consolidar + Filtros", 0)
liga("Loop · demais páginas", "É sentinela? (demais)", 1)
liga("É sentinela? (demais)", "Loop · demais páginas", 0)
liga("É sentinela? (demais)", "PNCP · consultar demais páginas", 1)
liga("Repetir? (demais)", "Aguardar (demais)", 0)
liga("Repetir? (demais)", "Loop · demais páginas", 1)
for a, b in [("Configuração", "Fila · página 1"), ("Fila · página 1", "Loop · página 1"),
             ("PNCP · consultar página 1", "Repetir? (p1)"), ("Aguardar (p1)", "PNCP · consultar página 1"),
             ("Fila · demais páginas", "Loop · demais páginas"),
             ("PNCP · consultar demais páginas", "Repetir? (demais)"), ("Aguardar (demais)", "PNCP · consultar demais páginas"),
             ("Consolidar + Filtros", "Há oportunidades?"),
             ("Montar prompt · Triagem", "Agente Triagem · Gemini"), ("Agente Triagem · Gemini", "Aplicar triagem"),
             ("Aplicar triagem", "Selecionar para análise"), ("Selecionar para análise", "Loop · processos"),
             ("Worker · pastas + downloads", "Montar prompt · Analista"), ("Montar prompt · Analista", "Agente Analista · Gemini"),
             ("Agente Analista · Gemini", "Montar prompt · Auditor"), ("Montar prompt · Auditor", "Agente Auditor · Claude"),
             ("Agente Auditor · Claude", "Consolidar análise"), ("Consolidar análise", "Agente Revisor · ChatGPT (opcional)"),
             ("Agente Revisor · ChatGPT (opcional)", "Aplicar revisão"), ("Aplicar revisão", "Worker · candidatos do catálogo"),
             ("Worker · candidatos do catálogo", "Montar prompt · Cruzamento"), ("Montar prompt · Cruzamento", "Há itens p/ cruzamento?"),
             ("Agente Cruzamento · Claude", "Aplicar cruzamento"), ("Aplicar cruzamento", "Worker · gravar análise e declarações"),
             ("Worker · gravar análise e declarações", "Retornar ao loop"), ("Retornar ao loop", "Loop · processos"),
             ("Montar payload · Relatório", "Worker · gerar relatório Excel"),
             ("Worker · gerar relatório Excel", "Resumo da execução")]:
    liga(a, b)
liga("Há oportunidades?", "Montar prompt · Triagem", 0)
liga("Há oportunidades?", "Montar payload · Relatório", 1)
liga("Loop · processos", "Montar payload · Relatório", 0)   # done
liga("Loop · processos", "É item real?", 1)                 # loop
liga("É item real?", "Worker · pastas + downloads", 0)
liga("É item real?", "Loop · processos", 1)
liga("Há itens p/ cruzamento?", "Agente Cruzamento · Claude", 0)
liga("Há itens p/ cruzamento?", "Aplicar cruzamento", 1)


# ------------------------------------------------------------------ envio por e-mail (um relatório por destinatário)
code("Envios por destinatário", "13_envios.js", [3560, -640])
http_post("Worker · relatório do destinatário", WORKER + "/relatorio", "={{ JSON.stringify($json.payload) }}", [3780, -640], timeout=300000)
node("Worker · baixar anexo", "n8n-nodes-base.httpRequest", 4.2, {
    "url": WORKER + "/relatorio/arquivo", "sendQuery": True,
    "queryParameters": {"parameters": [{"name": "nome", "value": "={{ $json.nome }}"}]},
    "options": {"response": {"response": {"responseFormat": "file", "outputPropertyName": "data"}}, "timeout": 120000}},
    [4000, -640], **RETRY)
MSG = ("={{ (() => { const e = $('Envios por destinatário').item.json; const r = $('Worker · relatório do destinatário').item.json; "
       "const ufs = e.ufs.join(', ').replace(/, ([^,]*)$/, ' e $1'); return `<p>Prezados,</p><p>Segue em anexo o relatório de oportunidades de licitação de <b>${ufs}</b>, "
       "com encerramento de propostas no período de <b>${e.janela}</b>.</p><p>Foram identificados <b>${r.qtd ?? 0}</b> ${(r.qtd ?? 0) === 1 ? 'processo aderente' : 'processos aderentes'} ao nosso portfólio. "
       "O arquivo traz o painel resumo, a lista completa com os links de cada processo e as colunas Situação, Vencido/Não Vencido e Observações para preenchimento.</p>"
       "<p>Anexo: ${r.nome || 'relatório'}</p><p>Atenciosamente,<br>${$('Configuração').first().json.assinatura}</p>"
       "<p style=\"color:#888888;font-size:10px;font-style:italic\">Relatório gerado automaticamente a partir das APIs oficiais do PNCP (licitacoes-pncp-ia). Serve de apoio à triagem e não dispensa a análise de cada edital antes da participação.</p>`; })() }}")
node("Enviar e-mail (SMTP)", "n8n-nodes-base.emailSend", 2.1, {
    "fromEmail": "={{ $('Configuração').first().json.remetente }}",
    "toEmail": "={{ $('Envios por destinatário').item.json.para }}",
    "subject": "={{ 'Relatório de Pregões — ' + $('Envios por destinatário').item.json.janela + ' — ' + $('Envios por destinatário').item.json.ufs.join(', ') }}",
    "emailFormat": "html", "html": MSG,
    "options": {"appendAttribution": False, "attachments": "data"}},
    [4220, -640], webhookId=uid("Enviar e-mail", "webhook"),
    credentials={"smtp": {"name": "SMTP"}},
    notes="Credencial SMTP. Gmail: smtp.gmail.com, porta 465, SSL, senha de app (myaccount.google.com/apppasswords).")
liga("Worker · gerar relatório Excel", "Envios por destinatário")
liga("Envios por destinatário", "Worker · relatório do destinatário")
liga("Worker · relatório do destinatário", "Worker · baixar anexo")
liga("Worker · baixar anexo", "Enviar e-mail (SMTP)")

# credenciais: crie no n8n com estes nomes (ou selecione as suas em cada nó depois de importar)
CRED_GEMINI = {"httpHeaderAuth": {"name": "Gemini API"}}
CRED_CLAUDE = {"httpHeaderAuth": {"name": "Anthropic API"}}
for n_ in nodes:
    if n_["name"] in ("Agente Triagem · Gemini", "Agente Analista · Gemini"):
        n_["credentials"] = CRED_GEMINI
    elif n_["name"] in ("Agente Auditor · Claude", "Agente Cruzamento · Claude"):
        n_["credentials"] = CRED_CLAUDE
    elif n_["name"] == "Agente Revisor · ChatGPT (opcional)":
        # Header Auth: Name = Authorization · Value = "Bearer sk-..."; ative o nó quando a conta OpenAI tiver créditos
        n_["credentials"] = {"httpHeaderAuth": {"name": "OpenAI API"}}
    elif n_["name"] == "Worker · pastas + downloads":
        # PNCP de documentos pode cair: o worker já tem disjuntor; não repetir 5× uma chamada longa
        n_["maxTries"] = 2
        n_["parameters"]["options"]["timeout"] = 600000

# ------------------------------------------------------------------ notas
nota("## Licitações PNCP IA · Captação + Análise IA + Relatório\n"
     "**Fonte:** API oficial do PNCP (todas as modalidades com proposta aberta). BLL, BNC, Portal de Compras Públicas, "
     "Compras.gov.br etc. entram porque publicam no PNCP (art. 54/174 da Lei 14.133).\n\n"
     "**Janela:** execução + 3 dias → 15 dias corridos (edite em *Configuração*).\n\n"
     "**Limite do PNCP:** a API bloqueia o IP (HTTP 429) com rajadas. Captação: 1 página por vez, pausa de 1,5 s, espera progressiva 15 s→5 min e filtro aplicado página a página. Duração típica: 25–40 min.",
     [-240, -520], 520, 300, 6)
nota("## Credenciais (Header Auth)\n"
     "1. **Gemini API** → Name `x-goog-api-key`, Value = chave do Google AI Studio\n"
     "2. **Anthropic API** → Name `x-api-key`, Value = chave do console.anthropic.com\n"
     "3. **OpenAI API** (opcional) → Name `Authorization`, Value `Bearer sk-...`\n\n"
     "⚠️ Assinaturas Claude Pro / ChatGPT Plus / Gemini **não** incluem API. Elas entram pelo **servidor MCP** "
     "(porta 8766) para consultar os processos e registrar pareceres.",
     [1760, -520], 560, 300, 3)
nota("## Loop por processo\nDownload (worker) → **Analista Gemini** (leitura integral, cita arquivo·página·cláusula) → "
     "**Auditor Claude** (confere, corrige, caça declarações espalhadas e redige modelos) → **Revisor ChatGPT** (opcional, "
     "ative o nó) → grava `00_RESUMO_DO_PROCESSO.md`, `02_MODELOS_DECLARACOES/*.docx` e `03_ANALISE_IA/`.",
     [3080, 140], 760, 200, 4)

wf = {
    "name": "Licitações PNCP IA · Captação PNCP + Agentes IA + Relatório",
    "nodes": nodes,
    "connections": conns,
    "settings": {"executionOrder": "v1", "timezone": "America/Sao_Paulo", "saveManualExecutions": True,
                 "callerPolicy": "workflowsFromSameOwner"},
    "pinData": {},
    "meta": {"templateCredsSetupCompleted": False},
    "tags": [],
}
saida = AQUI / "LICITACOES_PNCP_IA.json"
saida.write_text(json.dumps(wf, ensure_ascii=False, indent=2), encoding="utf-8")
print(saida, len(nodes), "nós")
