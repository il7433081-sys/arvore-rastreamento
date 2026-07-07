param(
    [string]$Commit = "HEAD"
)

$ErrorActionPreference = "Stop"
$RaizRepo = $PSScriptRoot
$AppDestino = Join-Path (Split-Path $RaizRepo -Parent) "Projetos_Python\app_ordem_servico"
$AppEspelho = Join-Path $RaizRepo "app_ordem_servico"

$arquivos = @(
    "permissoes_arvore_os.py",
    "perfis_app.py",
    "atividade_log.py",
    "presenca_telespectador.py",
    "agendamentos.py",
    "app.py",
    "templates\index.html"
)

if (-not (Test-Path $AppDestino)) {
    Write-Error "App destino nao encontrado: $AppDestino"
}

Push-Location $RaizRepo
try {
    if ($Commit -ne "HEAD") {
        git checkout $Commit -- app_ordem_servico/
        Write-Host "Checkout do commit $Commit aplicado no espelho local."
    }
} finally {
    Pop-Location
}

foreach ($rel in $arquivos) {
    $orig = Join-Path $AppEspelho $rel
    $dest = Join-Path $AppDestino $rel
    if (-not (Test-Path $orig)) {
        Write-Error "Arquivo ausente no checkpoint: $orig"
    }
    $dir = Split-Path $dest -Parent
    if (-not (Test-Path $dir)) {
        New-Item -ItemType Directory -Force -Path $dir | Out-Null
    }
    Copy-Item $orig $dest -Force
    Write-Host "  restaurado: $rel"
}

Write-Host ""
Write-Host "Restauracao concluida em $AppDestino" -ForegroundColor Green
Write-Host "Reinicie o servidor Flask e use Ctrl+F5 no navegador."
