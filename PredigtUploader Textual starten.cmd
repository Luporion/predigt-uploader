@echo off
chcp 65001 >nul
setlocal
title PredigtUploader Textual starten

cd /d "%~dp0"

echo PredigtUploader Textual wird gestartet.
echo Textual ist die experimentelle Oberflaeche. Der normale Wizard bleibt der produktive Standard.
echo.

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\run-tui.ps1"
set "EXITCODE=%ERRORLEVEL%"

echo.
if not "%EXITCODE%"=="0" (
    echo Die Textual-Oberflaeche wurde mit einem Fehler beendet.
    echo Bitte lies die Meldung oben. Wenn du nicht weiterkommst, gib die Logdatei an die Technik weiter.
) else (
    echo Die Textual-Oberflaeche wurde beendet.
)
echo.
echo Druecke eine Taste, um dieses Fenster zu schliessen.
pause >nul
exit /b %EXITCODE%
