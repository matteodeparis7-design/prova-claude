@echo off
title Scarico il video SuperFreddo 4K
cd /d "%~dp0"
echo.
echo  Sto scaricando il video SuperFreddo 4K (circa 500 MB).
echo  Non chiudere questa finestra, ci vogliono alcuni minuti.
echo.
echo  Scarico la parte 1 di 5...
curl -L -# -o "SF_parte1.tmp" "https://raw.githubusercontent.com/matteodeparis7-design/prova-claude/claude/fervent-einstein-qyvvjb/video_DEFINITIVO/4K_DA_SCARICARE/SuperFreddo_4K.mp4.pezzo1"
if errorlevel 1 goto errore
echo  Scarico la parte 2 di 5...
curl -L -# -o "SF_parte2.tmp" "https://raw.githubusercontent.com/matteodeparis7-design/prova-claude/claude/fervent-einstein-qyvvjb/video_DEFINITIVO/4K_DA_SCARICARE/SuperFreddo_4K.mp4.pezzo2"
if errorlevel 1 goto errore
echo  Scarico la parte 3 di 5...
curl -L -# -o "SF_parte3.tmp" "https://raw.githubusercontent.com/matteodeparis7-design/prova-claude/claude/fervent-einstein-qyvvjb/video_DEFINITIVO/4K_DA_SCARICARE/SuperFreddo_4K.mp4.pezzo3"
if errorlevel 1 goto errore
echo  Scarico la parte 4 di 5...
curl -L -# -o "SF_parte4.tmp" "https://raw.githubusercontent.com/matteodeparis7-design/prova-claude/claude/fervent-einstein-qyvvjb/video_DEFINITIVO/4K_DA_SCARICARE/SuperFreddo_4K.mp4.pezzo4"
if errorlevel 1 goto errore
echo  Scarico la parte 5 di 5...
curl -L -# -o "SF_parte5.tmp" "https://raw.githubusercontent.com/matteodeparis7-design/prova-claude/claude/fervent-einstein-qyvvjb/video_DEFINITIVO/4K_DA_SCARICARE/SuperFreddo_4K.mp4.pezzo5"
if errorlevel 1 goto errore
echo  Unisco le parti...
copy /b SF_parte1.tmp + SF_parte2.tmp + SF_parte3.tmp + SF_parte4.tmp + SF_parte5.tmp "SuperFreddo_DEFINITIVO_4K.mp4" >nul
del SF_parte1.tmp SF_parte2.tmp SF_parte3.tmp SF_parte4.tmp SF_parte5.tmp
echo.
echo  FATTO! Il video "SuperFreddo_DEFINITIVO_4K.mp4" e nella stessa cartella di questo file (di solito Download). Ora la apro.
echo.
explorer /select,"%~dp0SuperFreddo_DEFINITIVO_4K.mp4"
pause
exit /b
:errore
echo.
echo  Errore nel download: controlla la connessione internet e riprova.
pause
