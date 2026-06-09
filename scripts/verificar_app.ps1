param(
    [switch]$SemFrontend
)

$ErrorActionPreference = "Stop"
$Raiz = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Raiz

uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv run detect-secrets scan --all-files --exclude-files "apps/desktop/.*|docs/.*|README.md" | Out-Null

if (-not $SemFrontend) {
    Push-Location "apps\desktop"
    npm install
    npm run test
    npm run build
    Pop-Location
}

Write-Host "Verificacao do app concluida." -ForegroundColor Green
