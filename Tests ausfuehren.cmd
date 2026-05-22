@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo PredigtUploader Tests starten
echo =============================
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "scripts\test.ps1"
set EXITCODE=%ERRORLEVEL%
echo.
echo Druecke eine Taste, um dieses Fenster zu schliessen.
pause >nul
exit /b %EXITCODE%
