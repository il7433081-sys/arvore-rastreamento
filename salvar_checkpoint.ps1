param(
    [Parameter(Mandatory = $true)]
    [string]$Mensagem
)

$ErrorActionPreference = "Stop"
$RaizRepo = $PSScriptRoot
$AppDestino = Join-Path $RaizRepo "app_ordem_servico"
$AppOrigem = Join-Path (Split-Path $RaizRepo -Parent) "Projetos_Python\app_ordem_servico"

$arquivos = @(
    "permissoes_arvore_os.py",
    "perfis_app.py",
    "atividade_log.py",
    "presenca_telespectador.py",
    "agendamentos.py",
    "app.py",
    "templates\index.html"
)

if (-not (Test-Path $AppOrigem)) {
    Write-Error "App nao encontrado: $AppOrigem"
}

New-Item -ItemType Directory -Force -Path (Join-Path $AppDestino "templates") | Out-Null

foreach ($rel in $arquivos) {
    $orig = Join-Path $AppOrigem $rel
    $dest = Join-Path $AppDestino $rel
    if (-not (Test-Path $orig)) {
        Write-Error "Arquivo ausente no app: $orig"
    }
    Copy-Item $orig $dest -Force
    Write-Host "  copiado: $rel"
}

Push-Location $RaizRepo
try {
    git add -A
    $status = git status --porcelain
    if (-not $status) {
        Write-Host "Nenhuma alteracao para commitar (ja esta igual ao ultimo checkpoint)."
        exit 0
    }
    git commit -m $Mensagem
    Write-Host ""
    Write-Host "Checkpoint salvo:" -ForegroundColor Green
    git log -1 --oneline
} finally {
    Pop-Location
}
