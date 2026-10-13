# licitacoes-pncp-ia — exporta do computador ANTIGO tudo o que o INSTALAR.bat precisa no computador novo:
#   workflows.json   -> fluxos do n8n como estão em produção (inclusive o nó Configuração preenchido)
#   credenciais.json -> credenciais do n8n (Gemini, Anthropic, OpenAI, SMTP) - CONTÉM CHAVES EM TEXTO ABERTO
#   _CATALOGOS\      -> tabelas de preço usadas no cruzamento
# A pasta MIGRACAO_* fica dentro do repositório, mas o .gitignore impede que vá para o GitHub.
$ErrorActionPreference = 'Continue'   # comandos nativos (docker) escrevem no stderr; os erros são checados por $LASTEXITCODE
$Instalar = $PSScriptRoot
$Repo = Split-Path $Instalar -Parent
$Saida = Join-Path $Repo ("MIGRACAO_" + (Get-Date -Format 'yyyy-MM-dd_HHmm'))

function Ok($t)    { Write-Host "    [ok] $t" -ForegroundColor Green }
function Aviso($t) { Write-Host "    [!] $t" -ForegroundColor Yellow }

try {
    docker info 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) { throw 'O Docker não está rodando. Abra o Docker Desktop e tente de novo.' }
    $nomes = docker ps --format '{{.Names}}'
    if ($nomes -notcontains 'licitacoes-n8n') { throw 'O container "licitacoes-n8n" não está rodando neste computador.' }

    New-Item -ItemType Directory -Force -Path $Saida | Out-Null
    docker exec licitacoes-n8n sh -c 'rm -rf /tmp/mig && mkdir -p /tmp/mig' | Out-Null
    docker exec licitacoes-n8n n8n export:workflow --all --output=/tmp/mig/workflows.json
    if ($LASTEXITCODE -ne 0) { throw 'Falha ao exportar os fluxos.' }
    docker exec licitacoes-n8n n8n export:credentials --all --decrypted --output=/tmp/mig/credenciais.json
    if ($LASTEXITCODE -ne 0) { throw 'Falha ao exportar as credenciais.' }
    docker cp licitacoes-n8n:/tmp/mig/workflows.json (Join-Path $Saida 'workflows.json') | Out-Null
    docker cp licitacoes-n8n:/tmp/mig/credenciais.json (Join-Path $Saida 'credenciais.json') | Out-Null
    docker exec licitacoes-n8n rm -rf /tmp/mig | Out-Null
    Ok 'Fluxos e credenciais exportados.'

    $padrao = Join-Path ([Environment]::GetFolderPath('Desktop')) 'LICITACOES'
    $r = Read-Host "Pasta de dados LICITACOES [$padrao]"
    $Dados = if ([string]::IsNullOrWhiteSpace($r)) { $padrao } else { $r.Trim() }
    $cat = Join-Path $Dados '_CATALOGOS'
    if (Test-Path $cat) {
        Copy-Item -Path $cat -Destination (Join-Path $Saida '_CATALOGOS') -Recurse -Force
        Ok 'Tabelas de preço copiadas.'
    } else { Aviso "Não encontrei $cat" }

    Write-Host ''
    Write-Host "Pronto: $Saida" -ForegroundColor Cyan
    Write-Host ''
    Aviso 'credenciais.json contém as chaves das APIs e a senha do SMTP em texto aberto.'
    Aviso 'Leve a pasta para o computador novo por meio seguro e APAGUE-A depois da instalação.'
    Write-Host ''
    Write-Host 'No computador novo: clone/baixe o repositório, coloque a pasta MIGRACAO_* dentro dele e rode INSTALAR.bat.'
    Write-Host 'Os processos e editais já baixados (pasta LICITACOES) podem ser copiados à parte, se quiser mantê-los.'
    Start-Process explorer.exe $Saida
}
catch {
    Write-Host "ERRO: $($_.Exception.Message)" -ForegroundColor Red
}
