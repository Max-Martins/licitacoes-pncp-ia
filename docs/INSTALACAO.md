# Instalação passo a passo

Tempo estimado: 20 minutos, a maior parte esperando o Docker baixar as imagens na primeira vez.

## 1. O que você precisa

| Item | Onde conseguir | Obrigatório? |
|---|---|---|
| Computador Windows 10/11, macOS ou Linux, ligado no horário do agendamento | — | Sim |
| Docker Desktop (Windows/macOS) ou Docker Engine (Linux) | [docker.com](https://www.docker.com/products/docker-desktop/) | Sim |
| Chave da API do Gemini (triagem) | [aistudio.google.com/apikey](https://aistudio.google.com/apikey) · gratuita | Sim |
| Chave da API da Anthropic (leitura do edital e cruzamento) | [console.anthropic.com](https://console.anthropic.com) · paga por uso | Recomendada |
| Conta de e-mail com SMTP (envio do relatório) | Gmail: [senha de app](https://myaccount.google.com/apppasswords) | Opcional |

> As assinaturas Claude Pro, ChatGPT Plus e Gemini Advanced **não** incluem acesso à API. Elas podem usar os dados pelo servidor MCP (seção [MCP](#mcp)).

## 2. Rodar o instalador

1. Baixe o projeto (**Code → Download ZIP**) e descompacte numa pasta sua, por exemplo `Documentos\licitacoes-pncp-ia`.
2. Abra o Docker Desktop e espere ele indicar que está rodando.
3. Rode o instalador:
   - **Windows:** dois cliques em `INSTALAR.bat`. Se o Windows perguntar, permita a execução.
   - **macOS / Linux:** abra o terminal na pasta e digite `bash instalar.sh`.
4. Responda às perguntas (ENTER aceita o padrão):
   - **Pasta de dados:** onde ficam editais, relatórios e tabelas de preço. Padrão: `LICITACOES` na Área de Trabalho (Windows) ou na sua pasta pessoal (macOS/Linux).
   - **Energia (Windows):** impede que o computador durma na tomada. Sem isso o agendamento não roda.
5. No fim, o n8n abre no navegador (`http://localhost:5678`, ou outra porta se essa estiver ocupada).

O instalador pode ser rodado de novo quantas vezes quiser: ele reaproveita a configuração e não apaga nada.

## 3. Configurar o n8n

### 3.1 Primeiro acesso
Crie o usuário e a senha do n8n. Eles ficam só no seu computador.

### 3.2 Credenciais
Menu **Credentials → Create credential**:

| Nome (use exatamente este) | Tipo | Campos |
|---|---|---|
| `Gemini API` | Header Auth | Name: `x-goog-api-key` · Value: sua chave do Gemini |
| `Anthropic API` | Header Auth | Name: `x-api-key` · Value: sua chave da Anthropic |
| `SMTP` | SMTP | Gmail: User = seu e-mail · Password = senha de app · Host `smtp.gmail.com` · Port `465` · SSL/TLS ligado |
| `OpenAI API` (opcional) | Header Auth | Name: `Authorization` · Value: `Bearer sua-chave` |

Depois abra o fluxo **Licitações PNCP IA** e confira se cada nó de IA e o nó **Enviar e-mail (SMTP)** mostram a credencial certa. Se algum aparecer com aviso vermelho, clique nele e selecione a credencial na lista.

### 3.3 Nó Configuração
Dois cliques no nó **Configuração** e edite só o bloco `CONFIG`:

- `ufs`: estados pesquisados.
- `remetente`: precisa ser a mesma conta da credencial SMTP.
- `envios`: quem recebe o relatório e de quais UFs.
- `empresa`: razão social, CNPJ, endereço, representante (vão para a proposta e as declarações), `portfolio` e `criteriosTriagem` (orientam a IA).

Salve com **Ctrl+S**. Detalhes de cada campo em [PERSONALIZAR.md](PERSONALIZAR.md).

### 3.4 Testar e ativar
1. Clique em **Execute workflow**. A captação leva de 15 a 40 minutos, conforme o número de UFs (o PNCP bloqueia quem consulta rápido demais, então o fluxo vai devagar de propósito).
2. Confira a pasta `LICITACOES/_RELATORIOS` e o e-mail.
3. Clique em **Publish**. A partir daí o fluxo roda sozinho nos dias 1 e 16 de cada mês, às 07:00.

> No Docker Desktop, ligue *Settings › General › Start Docker Desktop when you sign in*, para tudo voltar sozinho depois de reiniciar o computador.

## 4. Tabelas de preço (opcional)

Coloque um arquivo `.xlsx` (ou `.xls`) por tabela em `LICITACOES/_CATALOGOS`. Basta ter as colunas **ITEM** (ou CÓDIGO), **DESCRIÇÃO**, **MARCA** e **PREÇO** (ou VALOR); o cabeçalho pode estar em qualquer uma das 30 primeiras linhas. Para atualizar, substitua o arquivo: não precisa reiniciar nada. Sem tabelas, o sistema funciona normalmente, só não faz o cruzamento nem a proposta prévia.

## 5. Mudar de computador

| Computador antigo | Computador novo |
|---|---|
| Dois cliques em `EXPORTAR_PARA_NOVO_PC.bat`. Ele cria `MIGRACAO_AAAA-MM-DD_HHMM` com o fluxo, as credenciais e as tabelas. | Coloque a pasta `MIGRACAO_*` dentro do projeto e rode `INSTALAR.bat`. Tudo é importado. |

> ⚠️ `credenciais.json` contém as chaves e a senha do e-mail **em texto aberto**. Leve por meio seguro e apague depois. O `.gitignore` impede que ele vá para o GitHub.

## MCP

O worker publica um servidor MCP em `http://localhost:8766/mcp` com as ferramentas `listar_oportunidades`, `detalhar_processo`, `ler_documento`, `buscar_no_edital`, `registrar_parecer` e `ler_pareceres`.

| Cliente | Configuração |
|---|---|
| Claude Code | `claude mcp add --transport http licitacoes-pncp http://localhost:8766/mcp` |
| Claude Desktop | em `claude_desktop_config.json`: `{"mcpServers":{"licitacoes-pncp":{"command":"npx","args":["-y","mcp-remote","http://localhost:8766/mcp"]}}}` |
| Codex | em `~/.codex/config.toml`: `[mcp_servers.licitacoes-pncp]`, `command = "npx"`, `args = ["-y","mcp-remote","http://localhost:8766/mcp"]` |
| Gemini CLI | em `~/.gemini/settings.json`: `{"mcpServers":{"licitacoes-pncp":{"httpUrl":"http://localhost:8766/mcp"}}}` |

Exemplo de pedido: *"Liste as oportunidades ALTA de MG, confira no edital a validade da proposta da primeira e registre seu parecer."* O parecer fica em `03_ANALISE_IA/pareceres.md` do processo, e o próximo assistente lê com `ler_pareceres`.

O servidor só aceita conexões do próprio computador. Não o exponha na internet sem autenticação.

## Problemas comuns

| Sintoma | O que fazer |
|---|---|
| `docker compose falhou` | Abra o Docker Desktop, espere ficar verde e rode o instalador de novo. |
| Worker não responde | Windows: `sistema\utilitarios\DIAGNOSTICO_WORKER.bat`. macOS/Linux: `docker logs licitacoes-worker`. |
| Relatório com aviso "páginas do PNCP falharam" | O PNCP estava instável. Execute o fluxo de novo mais tarde. |
| Processos sem edital na pasta | A API de documentos do PNCP estava fora. O worker tenta de novo a cada 30 minutos. |
| E-mail não chega | Confira a senha de app do Gmail e se o `remetente` é a mesma conta da credencial SMTP. |
| Não abra `localhost:5678/rest/...` no navegador | Esses endereços são internos do n8n e derrubam a sessão. |
