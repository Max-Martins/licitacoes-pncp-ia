#!/usr/bin/env bash
# licitacoes-pncp-ia - instalação no macOS e no Linux (n8n + worker + fluxo + pastas).
# Uso, na pasta do repositório:  bash instalar.sh
set -euo pipefail
REPO="$(cd "$(dirname "$0")" && pwd)"
INSTALAR="$REPO/instalar"

etapa() { printf '\n\033[36m==> %s\033[0m\n' "$1"; }
ok()    { printf '    \033[32m[ok]\033[0m %s\n' "$1"; }
aviso() { printf '    \033[33m[!]\033[0m %s\n' "$1"; }
erro()  { printf '\n\033[31mERRO: %s\033[0m\n' "$1"; exit 1; }
porta_livre() { ! (exec 3<>"/dev/tcp/127.0.0.1/$1") 2>/dev/null; }
esperar() { for _ in $(seq 1 "$2"); do curl -fs -o /dev/null "$1" && return 0; sleep 3; done; return 1; }

etapa 'Verificando o Docker'
command -v docker >/dev/null || erro 'Docker não encontrado. Instale o Docker Desktop (macOS) ou o Docker Engine (Linux) e rode de novo.'
docker info >/dev/null 2>&1 || erro 'O Docker está instalado, mas não está rodando. Abra o Docker e rode de novo.'
docker compose version >/dev/null 2>&1 || erro 'O plugin "docker compose" não está instalado.'
ok 'Docker rodando.'

etapa 'Pasta onde ficam os processos, editais e relatórios'
padrao="$HOME/LICITACOES"
read -r -p "Caminho da pasta de dados [$padrao]: " DADOS
DADOS="${DADOS:-$padrao}"
mkdir -p "$DADOS/_RELATORIOS" "$DADOS/_SISTEMA" "$DADOS/_CATALOGOS"
ok "Pasta pronta: $DADOS"

etapa 'Gerando a configuração local'
ENV_ARQ="$INSTALAR/.env"
CHAVE="$(grep -s '^N8N_ENCRYPTION_KEY=' "$ENV_ARQ" | cut -d= -f2- || true)"
[ -n "$CHAVE" ] || CHAVE="$(od -An -N32 -tx1 /dev/urandom | tr -d ' \n')"
EXISTENTES="$(docker ps -a --format '{{.Names}}')"
PORTA=5678
if ! grep -qx licitacoes-n8n <<<"$EXISTENTES" && ! porta_livre $PORTA; then
  aviso 'A porta 5678 já está em uso (outro n8n?). Ele NÃO será alterado; este n8n usará outra porta.'
  PORTA=5679; while ! porta_livre $PORTA; do PORTA=$((PORTA + 1)); done
fi
for p in 8765 8766; do
  grep -qx licitacoes-worker <<<"$EXISTENTES" || porta_livre $p || erro "A porta $p está em uso por outro programa. Libere-a e rode de novo."
done
# No Linux o worker grava na pasta com o seu usuário (no macOS o Docker Desktop cuida disso)
USUARIO="1000:1000"; [ "$(uname)" = Linux ] && USUARIO="$(id -u):$(id -g)"
printf 'LICITACOES_HOST_DIR=%s\nN8N_ENCRYPTION_KEY=%s\nN8N_PORTA=%s\nWORKER_USUARIO=%s\n' "$DADOS" "$CHAVE" "$PORTA" "$USUARIO" > "$ENV_ARQ"
chmod 600 "$ENV_ARQ"
ok 'Arquivo instalar/.env criado (fica só no seu computador).'

etapa 'Subindo n8n e worker (a primeira vez demora alguns minutos)'
(cd "$INSTALAR" && docker compose --env-file .env up -d --build) || erro 'docker compose falhou. Veja as mensagens acima.'
N8N="http://localhost:$PORTA"
esperar "$N8N/healthz" 60 || erro 'O n8n não respondeu em 3 minutos.'
ok "n8n no ar: $N8N"
if esperar 'http://localhost:8765/health' 40; then ok 'Worker no ar: http://localhost:8765/health'; else aviso 'Worker ainda não respondeu: docker logs licitacoes-worker'; fi

etapa 'Importando o fluxo no n8n'
docker cp "$REPO/sistema/n8n/LICITACOES_PNCP_IA.json" licitacoes-n8n:/tmp/fluxo.json >/dev/null
docker exec licitacoes-n8n n8n import:workflow --input=/tmp/fluxo.json || erro 'Falha ao importar o fluxo.'
docker exec licitacoes-n8n rm -f /tmp/fluxo.json
ok 'Fluxo "Licitações PNCP IA" importado.'

etapa 'Instalação concluída'
cat <<FIM

  Falta pouco. No navegador ($N8N):
   1. Crie o usuário do n8n (primeiro acesso).
   2. Crie as credenciais (Credentials > New) com estes nomes:
        - 'Gemini API'    (Header Auth: Name x-goog-api-key, Value = sua chave)
        - 'Anthropic API' (Header Auth: Name x-api-key,      Value = sua chave)
        - 'SMTP'          (SMTP do seu e-mail; no Gmail use senha de app)
   3. Abra o fluxo 'Licitações PNCP IA', preencha o nó 'Configuração' (empresa, UFs, e-mails) e salve.
   4. Coloque suas tabelas de preço (.xlsx) em $DADOS/_CATALOGOS (opcional).
   5. Clique em 'Execute workflow' para testar e depois em 'Publish' para ativar o agendamento.

  Guia completo: docs/INSTALACAO.md
FIM
if [ "$(uname)" = Darwin ]; then open "$N8N"; elif command -v xdg-open >/dev/null; then xdg-open "$N8N" >/dev/null 2>&1 || true; fi
