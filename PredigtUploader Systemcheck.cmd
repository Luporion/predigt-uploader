@echo off
setlocal
title PredigtUploader Systemcheck

cd /d "%~dp0"

echo PredigtUploader Systemcheck wird gestartet.
echo.

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\check-system.ps1"
set "EXITCODE=%ERRORLEVEL%"

echo.
if not "%EXITCODE%"=="0" (
    echo Der Systemcheck hat fehlende Punkte gefunden.
    echo Bitte lies die Hinweise oben und starte den Systemcheck danach erneut.
) else (
    echo Der Systemcheck ist abgeschlossen. Alles Wichtige sieht gut aus.
)
echo.
echo Druecke eine Taste, um dieses Fenster zu schliessen.
pause >nul
exit /b %EXITCODE%
