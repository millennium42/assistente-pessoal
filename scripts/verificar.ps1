param(
    [switch]$SemFormatacao
)

$ErrorActionPreference = "Stop"

function Invoke-Step {
    param(
        [string]$Nome,
        [scriptblock]$Comando
    )

    Write-Host ""
    Write-Host "==> $Nome" -ForegroundColor Cyan
    & $Comando
}

$Raiz = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Raiz

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    throw "Ambiente virtual nao encontrado. Rode: uv venv; uv pip install -e `".[dev]`""
}

Invoke-Step "Testes" {
    & ".venv\Scripts\python.exe" -m pytest
}

Invoke-Step "Lint" {
    & ".venv\Scripts\python.exe" -m ruff check .
}

if (-not $SemFormatacao) {
    Invoke-Step "Formatacao" {
        & ".venv\Scripts\python.exe" -m ruff format --check .
    }
}

Write-Host ""
Write-Host "Verificacao concluida com sucesso." -ForegroundColor Green

