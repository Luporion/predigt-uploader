@echo off
setlocal
title PredigtUploader starten

cd /d "%~dp0"

echo PredigtUploader wird gestartet.
echo.

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\run-wizard.ps1"
set "EXITCODE=%ERRORLEVEL%"

echo.
if not "%EXITCODE%"=="0" (
    echo Der PredigtUploader wurde mit einem Fehler beendet.
    echo Bitte lies die Meldung oben. Wenn du nicht weiterkommst, gib die Logdatei an die Technik weiter.
) else (
    echo Der PredigtUploader wurde beendet.
)
echo.
echo Druecke eine Taste, um dieses Fenster zu schliessen.
pause >nul
exit /b %EXITCODE%
