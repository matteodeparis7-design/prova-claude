@echo off
chcp 65001 >nul
title Promovo
cd /d "%~dp0promovo"

echo.
echo  =============================================
echo   PROMOVO - avvio sul tuo computer
echo  =============================================
echo.

set "PY="
where py >nul 2>nul && set "PY=py -3"
if not defined PY (
  where python >nul 2>nul && set "PY=python"
)
if not defined PY goto nopython
%PY% -c "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)" >nul 2>nul || goto nopython

if not exist ".venv\Scripts\python.exe" (
  echo  Prima installazione: servono alcuni minuti, solo questa volta.
  %PY% -m venv .venv || goto error
)
echo  Controllo dei componenti...
".venv\Scripts\python.exe" -m pip install --quiet --upgrade pip >nul 2>nul
".venv\Scripts\python.exe" -m pip install --quiet --upgrade . || goto error

if not defined ANTHROPIC_API_KEY set "PROMOVO_AI=off"

echo.
echo  Promovo si sta avviando: tra pochi secondi si apre il browser.
echo  Accesso di prova:  demo@promovo.it  /  promovo2026
echo.
echo  NON chiudere questa finestra mentre usi Promovo.
echo  Per spegnerlo, chiudi questa finestra.
echo.
start "" cmd /c "timeout /t 8 /nobreak >nul & start http://127.0.0.1:8000"
".venv\Scripts\python.exe" -m promovo --demo
pause
exit /b

:nopython
echo  Per usare Promovo serve Python 3.11 o piu' recente, che ancora non c'e'.
echo.
echo  1. Si apre ora la pagina di Python: premi "Download Python".
echo  2. Avvia il file scaricato e SPUNTA la casella "Add python.exe to PATH".
echo  3. Premi "Install Now" e, a installazione finita, riapri questo file.
echo.
start https://www.python.org/downloads/
pause
exit /b

:error
echo.
echo  Si e' verificato un errore durante l'installazione.
echo  Fai una foto di questa finestra e mandala in chat.
pause
exit /b
