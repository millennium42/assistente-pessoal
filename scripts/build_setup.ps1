$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

if (-not (Get-Command "uv" -ErrorAction SilentlyContinue)) {
    throw "uv nao encontrado. Rode .\scripts\bootstrap_windows.ps1 -InstalarDependenciasProjeto antes do build."
}

if (-not (Get-Command "npm" -ErrorAction SilentlyContinue)) {
    throw "npm nao encontrado. Instale Node.js antes de gerar o .exe."
}

if (-not (Get-Command "cargo" -ErrorAction SilentlyContinue)) {
    throw "cargo nao encontrado. Rode .\scripts\bootstrap_windows.ps1 -InstalarDependenciasProjeto e reinicie o terminal antes do build."
}

uv sync --extra dev

Push-Location "apps\desktop"
npm install
npm run tauri:build
Pop-Location

$BundleDir = Join-Path $Root "apps\desktop\src-tauri\target\release\bundle\nsis"
$Exe = Get-ChildItem -Path $BundleDir -Filter "*.exe" -ErrorAction SilentlyContinue |
    Sort-Object LastWriteTime -Descending |
    Select-Object -First 1

if (-not $Exe) {
    throw "Build concluido sem encontrar .exe em $BundleDir."
}

Write-Host "Executavel gerado: $($Exe.FullName)" -ForegroundColor Green
