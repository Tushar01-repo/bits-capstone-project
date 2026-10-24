param(
    [switch]$WithDocker,
    [switch]$WithBrowserTests
)
$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
function Invoke-Checked {
    param([string]$Executable, [string[]]$Arguments)
    & $Executable @Arguments
    if ($LASTEXITCODE -ne 0) { throw "Command failed: $Executable $($Arguments -join ' ')" }
}
if (-not (Test-Path '.venv/Scripts/python.exe')) {
    Invoke-Checked 'py' @('-3.12','-m','venv','.venv')
}
$python = (Resolve-Path '.venv/Scripts/python.exe').Path
Invoke-Checked $python @('-m','pip','install','-r','requirements.txt')
Invoke-Checked $python @('golden_path.py')
if ($WithBrowserTests) {
    if (-not (Get-Command npm -ErrorAction SilentlyContinue)) { throw 'Install Node.js/npm, then rerun with -WithBrowserTests.' }
    Invoke-Checked 'npm' @('install','--no-save','--package-lock=false','playwright@1.62.1')
    Invoke-Checked 'npx' @('playwright','install','chromium')
    $env:PYTHON = $python
    Invoke-Checked 'node' @('tests/browser.cjs')
}
if ($WithDocker) {
    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) { throw 'Docker is not installed. Install and start Docker Desktop, then rerun with -WithDocker.' }
    Invoke-Checked 'docker' @('compose','version')
    Invoke-Checked 'docker' @('compose','build')
    Invoke-Checked 'docker' @('compose','run','--rm','train')
    Invoke-Checked 'docker' @('compose','--profile','monitoring','up','-d','--wait','app','prometheus')
    Invoke-Checked 'docker' @('compose','ps')
    Invoke-RestMethod 'http://127.0.0.1:8000/health'
    Write-Host 'Dashboard: http://127.0.0.1:8000 | Prometheus: http://127.0.0.1:9090'
} else {
    Write-Host 'Checks complete. Starting dashboard at http://127.0.0.1:8000. Ctrl+C stops it.'
    Invoke-Checked $python @('-m','newsml.server')
}
