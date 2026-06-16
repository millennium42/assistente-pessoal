param(
    [switch]$SomenteVerificar,
    [switch]$InstalarDependenciasProjeto
)

$ErrorActionPreference = "Stop"

function Test-CommandOrPath {
    param(
        [string]$Nome,
        [string[]]$Fallbacks
    )

    if (Get-Command $Nome -ErrorAction SilentlyContinue) {
        return $true
    }

    foreach ($Fallback in $Fallbacks) {
        if (Test-Path $Fallback) {
            return $true
        }
    }

    return $false
}

function Install-WingetPackage {
    param(
        [string]$Id,
        [string]$Nome
    )

    Write-Host "Instalando $Nome ($Id)..." -ForegroundColor Cyan
    winget install `
        --source winget `
        --accept-source-agreements `
        --accept-package-agreements `
        --silent `
        --disable-interactivity `
        --id $Id `
        --exact
}

function Resolve-Tool {
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
    throw "Nao encontrei $Nome. Reinicie o terminal ou rode este script sem -SomenteVerificar."
}

$Raiz = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Raiz

$Ferramentas = @(
    @{
        Nome = "Python 3.12"
        Id = "Python.Python.3.12"
        Comando = "python"
        Fallbacks = @("$env:LocalAppData\Programs\Python\Python312\python.exe")
    },
    @{
        Nome = "uv"
        Id = "astral-sh.uv"
        Comando = "uv"
        Fallbacks = @("$env:LocalAppData\Microsoft\WinGet\Links\uv.exe")
    },
    @{
        Nome = "FFmpeg"
        Id = "Gyan.FFmpeg"
        Comando = "ffmpeg"
        Fallbacks = @("$env:LocalAppData\Microsoft\WinGet\Links\ffmpeg.exe")
    }
)

foreach ($Ferramenta in $Ferramentas) {
    $Existe = Test-CommandOrPath -Nome $Ferramenta.Comando -Fallbacks $Ferramenta.Fallbacks
    if ($Existe) {
        Write-Host "$($Ferramenta.Nome): encontrado" -ForegroundColor Green
        continue
    }

    if ($SomenteVerificar) {
        Write-Host "$($Ferramenta.Nome): faltando" -ForegroundColor Yellow
        continue
    }

    Install-WingetPackage -Id $Ferramenta.Id -Nome $Ferramenta.Nome
}

if ($SomenteVerificar) {
    Write-Host ""
    Write-Host "Verificacao de bootstrap concluida." -ForegroundColor Green
    exit 0
}

if ($InstalarDependenciasProjeto) {
    $Uv = Resolve-Tool -Nome "uv" -Fallback "$env:LocalAppData\Microsoft\WinGet\Links\uv.exe"
    $Python = Resolve-Tool -Nome "python" -Fallback "$env:LocalAppData\Programs\Python\Python312\python.exe"

    Write-Host ""
    Write-Host "Criando ambiente virtual e instalando o projeto..." -ForegroundColor Cyan
    & $Uv venv --python $Python
    & $Uv pip install -e ".[dev]"
}

Write-Host ""
Write-Host "Bootstrap concluido. Se algum comando nao aparecer no PATH, reinicie o terminal." -ForegroundColor Green
