@echo off
REM Roda o agente localmente e abre a página de resultados.
REM Opcional: defina sua chave do Gemini antes:  set GEMINI_API_KEY=xxxx
cd /d "%~dp0"
python -m pip install -q -r requirements.txt
python agente.py
start "" "docs\index.html"
