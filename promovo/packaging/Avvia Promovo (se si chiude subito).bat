@echo off
chcp 65001 >nul
title Promovo - avvio con messaggi
cd /d "%~dp0"
echo Avvio di Promovo...
echo.
"%~dp0Promovo.exe"
echo.
echo  ---------------------------------------------------------------
echo  Promovo si e' chiuso (codice %ERRORLEVEL%).
echo  Se non l'hai chiuso tu, fai una foto di questa finestra e mandala.
echo  ---------------------------------------------------------------
pause
