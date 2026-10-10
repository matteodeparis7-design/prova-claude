@echo off
cd /d "%~dp0"
echo Sto unendo i 5 pezzi del video 4K, attendi qualche secondo...
copy /b SuperFreddo_4K.mp4.pezzo1 + SuperFreddo_4K.mp4.pezzo2 + SuperFreddo_4K.mp4.pezzo3 + SuperFreddo_4K.mp4.pezzo4 + SuperFreddo_4K.mp4.pezzo5 SuperFreddo_DEFINITIVO_4K.mp4 >nul
echo.
echo FATTO! Il video si chiama SuperFreddo_DEFINITIVO_4K.mp4 ed e in questa cartella.
pause
