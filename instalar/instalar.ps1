# licitacoes-pncp-ia - instalação completa no Windows (n8n + worker + fluxo + pastas).
# Executado pelo INSTALAR.bat (duplo clique). Pode ser rodado de novo sem estragar nada.
$ErrorActionPreference = 'Continue'   # comandos nativos (docker) escrevem no stderr; os erros são checados por $LASTEXITCODE
$Instalar = $PSScriptRoot
$Repo = Split-Path $Instalar -Parent
$Log = Join-Path $Instalar 'instalacao.log'
Start-Transcript -Path $Log -Append | Out-Null

function Etapa($t) { Write-Host ''; Write-Host "==> $t" -ForegroundColor Cyan }
function Ok($t)    { Write-Host "    [ok] $t" -ForegroundColor Green }
function Aviso($t) { Write-Host "    [!] $t" -ForegroundColor Yellow }
function Pergunta($texto, $padrao) {
    $r = Read-Host "$texto [$padrao]"
    if ([string]::IsNullOrWhiteSpace($r)) { return $padrao } else { return $r.Trim() }
}
function Esperar-Url($url, $segundos) {
    $fim = (Get-Date).AddSeconds($segundos)
    while ((Get-Date) -lt $fim) {
        try { $r = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 5; if ($r.StatusCode -lt 500) { return $true } } catch {}
        Start-Sleep -Seconds 3
    }
    return $false
}
function Porta-Livre($porta) {
    return -not (Get-NetTCPConnection -LocalPort $porta -State Listen -ErrorAction SilentlyContinue)
}

try {
    # 1. Docker ---------------------------------------------------------------------------------
    Etapa 'Verificando o Docker Desktop'
    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
        Aviso 'Docker Desktop não encontrado.'
        if ((Pergunta 'Instalar agora pelo winget? (S/N)' 'S') -match '^[sS]') {
            winget install -e --id Docker.DockerDesktop --accept-package-agreements --accept-source-agreements
            Aviso 'Reinicie o computador, abra o Docker Desktop uma vez e rode o INSTALAR.bat de novo.'
        } else {
            Aviso 'Baixe em https://www.docker.com/products/docker-desktop/ e rode o INSTALAR.bat de novo.'
        }
        return
    }
    docker info 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Aviso 'O Docker está instalado, mas não está rodando. Abrindo o Docker Desktop...'
        $dd = Join-Path $env:ProgramFiles 'Docker\Docker\Docker Desktop.exe'
        if (Test-Path $dd) { Start-Process $dd }
        $fim = (Get-Date).AddMinutes(4)
        do { Start-Sleep 5; docker info 2>&1 | Out-Null } while ($LASTEXITCODE -ne 0 -and (Get-Date) -lt $fim)
        if ($LASTEXITCODE -ne 0) { throw 'O Docker não iniciou em 4 minutos. Abra o Docker Desktop e rode o INSTALAR.bat de novo.' }
    }
    Ok 'Docker rodando.'

    # 2. Pasta de dados ---------------------------------------------------------------------------
    Etapa 'Pasta onde ficam os processos, editais e relatórios'
    $padrao = Join-Path ([Environment]::GetFolderPath('Desktop')) 'LICITACOES'
    $Dados = Pergunta 'Caminho da pasta de dados' $padrao
    foreach ($sub in @('_RELATORIOS', '_SISTEMA', '_CATALOGOS')) {
        New-Item -ItemType Directory -Force -Path (Join-Path $Dados $sub) | Out-Null
    }
    Ok "Pasta pronta: $Dados"

    # 3. Pacote de migração (opcional) ------------------------------------------------------------
    $Migracao = Get-ChildItem -Path $Repo -Directory -Filter 'MIGRACAO*' -ErrorAction SilentlyContinue |
        Sort-Object Name -Descending | Select-Object -First 1
    if ($Migracao) {
        Ok "Pacote de migração encontrado: $($Migracao.Name)"
        if (Test-Path (Join-Path $Migracao.FullName '_CATALOGOS')) {
            Copy-Item -Path (Join-Path $Migracao.FullName '_CATALOGOS\*') -Destination (Join-Path $Dados '_CATALOGOS') -Recurse -Force
            Ok 'Tabelas de preço copiadas para _CATALOGOS.'
        }
    }

    # 4. Configuração (.env) ----------------------------------------------------------------------
    Etapa 'Gerando a configuração local'
    $Env = Join-Path $Instalar '.env'
    $chave = $null
    if (Test-Path $Env) {
        $linha = Select-String -Path $Env -Pattern '^N8N_ENCRYPTION_KEY=(.+)$' | Select-Object -First 1
        if ($linha) { $chave = $linha.Matches[0].Groups[1].Value }
    }
    if (-not $chave) { $chave = -join ((1..32) | ForEach-Object { '{0:x2}' -f (Get-Random -Maximum 256) }) }
    $existentes = docker ps -a --format '{{.Names}}'
    $Porta = 5678
    if (($existentes -notcontains 'licitacoes-n8n') -and -not (Porta-Livre $Porta)) {
        Aviso 'A porta 5678 já está em uso (outro n8n?). Ele NÃO será alterado; este n8n usará outra porta.'
        $Porta = 5679
        while (-not (Porta-Livre $Porta)) { $Porta++ }
    }
    foreach ($p in 8765, 8766) {
        if (($existentes -notcontains 'licitacoes-worker') -and -not (Porta-Livre $p)) { throw "A porta $p está em uso por outro programa. Libere-a e rode de novo." }
    }
    $hostDir = $Dados -replace '\\', '/'
    @("LICITACOES_HOST_DIR=$hostDir", "N8N_ENCRYPTION_KEY=$chave", "N8N_PORTA=$Porta") | Set-Content -Path $Env -Encoding ASCII
    Ok 'Arquivo instalar\.env criado (fica só no seu computador).'

    # 5. Containers -------------------------------------------------------------------------------
    Etapa 'Subindo n8n e worker (a primeira vez demora alguns minutos)'
    Push-Location $Instalar
    docker compose --env-file .env up -d --build
    $rc = $LASTEXITCODE
    Pop-Location
    if ($rc -ne 0) { throw 'docker compose falhou. Veja as mensagens acima.' }
    $N8n = "http://localhost:$Porta"
    if (-not (Esperar-Url "$N8n/healthz" 180)) { throw 'O n8n não respondeu em 3 minutos.' }
    Ok "n8n no ar: $N8n"
    if (Esperar-Url 'http://localhost:8765/health' 120) { Ok 'Worker no ar: http://localhost:8765/health' } else { Aviso 'Worker ainda não respondeu. Rode sistema\utilitarios\DIAGNOSTICO_WORKER.bat' }

    # 6. Importar fluxo e credenciais -------------------------------------------------------------
    Etapa 'Importando o fluxo no n8n'
    docker exec licitacoes-n8n mkdir -p /tmp/importar | Out-Null
    if ($Migracao -and (Test-Path (Join-Path $Migracao.FullName 'credenciais.json'))) {
        docker cp (Join-Path $Migracao.FullName 'credenciais.json') licitacoes-n8n:/tmp/importar/credenciais.json | Out-Null
        docker exec licitacoes-n8n n8n import:credentials --input=/tmp/importar/credenciais.json
        Ok 'Credenciais importadas.'
    }
    $wf = if ($Migracao -and (Test-Path (Join-Path $Migracao.FullName 'workflows.json'))) { Join-Path $Migracao.FullName 'workflows.json' }
          else { Join-Path $Repo 'sistema\n8n\LICITACOES_PNCP_IA.json' }
    docker cp $wf licitacoes-n8n:/tmp/importar/workflows.json | Out-Null
    docker exec licitacoes-n8n n8n import:workflow --input=/tmp/importar/workflows.json
    if ($LASTEXITCODE -ne 0) { throw 'Falha ao importar o fluxo.' }
    docker exec licitacoes-n8n rm -rf /tmp/importar | Out-Null
    Ok "Fluxo importado de: $wf"

    # 7. Energia (opcional) ----------------------------------------------------------------------
    Etapa 'Energia'
    if ((Pergunta 'Impedir que o Windows durma/hiberne na tomada (necessário para o agendamento)? (S/N)' 'S') -match '^[sS]') {
        foreach ($a in @('standby-timeout-ac 0', 'hibernate-timeout-ac 0')) {
            Start-Process powercfg -ArgumentList "/change $a" -NoNewWindow -Wait
        }
        Ok 'Suspensão e hibernação desativadas na tomada.'
    }

    # 8. Próximos passos -------------------------------------------------------------------------
    Etapa 'Instalação concluída'
    Write-Host @"

  Falta pouco. No navegador ($N8n):
   1. Crie o usuário do n8n (primeiro acesso).
   2. Crie as credenciais (Credentials > New) com estes nomes:
        - 'Gemini API'    (Header Auth: Name x-goog-api-key, Value = sua chave)
        - 'Anthropic API' (Header Auth: Name x-api-key,      Value = sua chave)
        - 'SMTP'          (SMTP do seu e-mail; no Gmail use senha de app)
   3. Abra o fluxo 'Licitações PNCP IA', preencha o nó 'Configuração' (empresa, UFs, e-mails) e salve.
   4. Coloque suas tabelas de preço (.xlsx) em $Dados\_CATALOGOS (opcional).
   5. Clique em 'Execute workflow' para testar e depois em 'Publish' para ativar o agendamento.

  Guia completo: docs\INSTALACAO.md   ·   Log desta instalação: $Log
"@
    Start-Process $N8n
}
catch {
    Write-Host ''
    Write-Host "ERRO: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host "Log: $Log"
}
finally {
    Stop-Transcript | Out-Null
}
