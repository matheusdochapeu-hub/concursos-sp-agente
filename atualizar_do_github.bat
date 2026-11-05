@echo off
REM Atualiza o projeto local com o GitHub e (opcionalmente) roda o agente.
chcp 65001 >nul
cd /d "%~dp0"

echo ===================================================
echo [1/3] Sincronizando com o GitHub (git pull)...
echo ===================================================
git pull origin main
if errorlevel 1 (
    echo.
    echo [ERRO] Falha ao atualizar pelo GitHub. Verifique conexao ou arquivos locais pendentes.
    pause
    exit /b %errorlevel%
)

echo.
echo ===================================================
echo [2/3] Atualizando dependencias Python...
echo ===================================================
python -m pip install -q -r requirements.txt

echo.
echo ===================================================
echo [3/3] Executando testes automatizados...
echo ===================================================
python -m unittest discover tests
if errorlevel 1 (
    echo.
    echo [AVISO] Alguns testes falharam.
    pause
    exit /b %errorlevel%
)

echo.
echo ===================================================
echo SUCESSO! O projeto foi atualizado com o GitHub.
echo ===================================================
echo.
set /p RODA="Deseja rodar o agente agora para coletar os editais de hoje? (S/N): "
if /i "%RODA%"=="S" (
    echo.
    echo Executando agente.py...
    python agente.py
    start "" "docs\index.html"
) else (
    echo Pronto! Nenhuma execucao necessaria.
)
pause
