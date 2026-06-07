param(
    [string]$Owner = "millennium42",
    [string]$Repo = "assistente-pessoal",
    [string]$Branch = "codex/v1-assistente-pessoal"
)

$ErrorActionPreference = "Stop"

function Resolve-CommandPath {
    param(
        [string]$Nome,
        [string]$Fallback
    )

    $Comando = Get-Command $Nome -ErrorAction SilentlyContinue
    if ($Comando) {
        return $Comando.Source
    }
    if (Test-Path $Fallback) {
        return $Fallback
    }
    throw "Nao encontrei $Nome. Instale a ferramenta ou reinicie o terminal para atualizar o PATH."
}

$Raiz = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Raiz

$Git = Resolve-CommandPath "git" "C:\Program Files\Git\cmd\git.exe"
$Gh = Resolve-CommandPath "gh" "C:\Program Files\GitHub CLI\gh.exe"

& $Gh auth status | Out-Null
if ($LASTEXITCODE -ne 0) {
    throw "GitHub CLI nao autenticado. Rode: gh auth login"
}

$NomeCompleto = "$Owner/$Repo"
$Url = "https://github.com/$NomeCompleto.git"

& $Gh repo view $NomeCompleto | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Criando repositorio publico $NomeCompleto..." -ForegroundColor Cyan
    & $Gh repo create $NomeCompleto --public --description "Assistente pessoal modular em Python com voz e memoria em Obsidian."
}

$RemoteAtual = & $Git remote get-url origin 2>$null
if ($LASTEXITCODE -eq 0) {
    & $Git remote set-url origin $Url
} else {
    & $Git remote add origin $Url
}

& $Git push -u origin $Branch

Write-Host "Publicado em https://github.com/$NomeCompleto" -ForegroundColor Green

