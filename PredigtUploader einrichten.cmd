@echo off
setlocal
title PredigtUploader einrichten

cd /d "%~dp0"

echo PredigtUploader wird eingerichtet.
echo.

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\setup-local.ps1"
set "EXITCODE=%ERRORLEVEL%"

echo.
if not "%EXITCODE%"=="0" (
    echo Die Einrichtung wurde mit einem Fehler beendet.
    echo Bitte lies die Meldung oben und starte die Einrichtung danach erneut.
) else (
    echo Die Einrichtung ist abgeschlossen.
    echo Danach kannst du "PredigtUploader Systemcheck.cmd" doppelklicken.
)
echo.
echo Druecke eine Taste, um dieses Fenster zu schliessen.
pause >nul
exit /b %EXITCODE%
