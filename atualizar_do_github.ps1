# Atualizar Concursos SP pelo GitHub
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

Write-Host "===================================================" -ForegroundColor Cyan
Write-Host "[1/3] Puxando atualizações do GitHub (git pull)..." -ForegroundColor Cyan
Write-Host "===================================================" -ForegroundColor Cyan
git pull origin main

Write-Host "`n===================================================" -ForegroundColor Cyan
Write-Host "[2/3] Instalando/atualizando dependências..." -ForegroundColor Cyan
Write-Host "===================================================" -ForegroundColor Cyan
python -m pip install -q -r requirements.txt

Write-Host "`n===================================================" -ForegroundColor Cyan
Write-Host "[3/3] Rodando bateria de testes..." -ForegroundColor Cyan
Write-Host "===================================================" -ForegroundColor Cyan
python -m unittest discover tests

Write-Host "`n===================================================" -ForegroundColor Green
Write-Host "SUCESSO! O projeto está 100% atualizado." -ForegroundColor Green
Write-Host "===================================================" -ForegroundColor Green

$resposta = Read-Host "Deseja rodar o agente agora para coletar os editais de hoje? (S/N)"
if ($resposta -match '^[sSyY]') {
    Write-Host "`nExecutando agente.py..." -ForegroundColor Yellow
    python agente.py
    Start-Process "docs\index.html"
}
