param(
    [string]$ReleaseTag = "",
    [string]$ReleaseName = ""
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
[Console]::InputEncoding = [System.Text.UTF8Encoding]::new($false)
$OutputEncoding = [Console]::OutputEncoding

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$TestScript = Join-Path $ScriptDir "test.ps1"
$ReleaseZipScript = Join-Path $ScriptDir "make-release-zip.ps1"

Write-Host "PredigtUploader Release-Ablauf"
Write-Host "=============================="
Write-Host ""

Write-Host "1. Tests werden ausgefuehrt..." -ForegroundColor Cyan
& $TestScript
if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "Release wird abgebrochen, weil Tests fehlgeschlagen sind." -ForegroundColor Red
    exit $LASTEXITCODE
}

Write-Host ""
Write-Host "2. Release-ZIP wird erstellt..." -ForegroundColor Cyan
if (-not [string]::IsNullOrWhiteSpace($ReleaseName)) {
    & $ReleaseZipScript -ReleaseName $ReleaseName
}
elseif (-not [string]::IsNullOrWhiteSpace($ReleaseTag)) {
    & $ReleaseZipScript -ReleaseTag $ReleaseTag
}
else {
    & $ReleaseZipScript
}
exit $LASTEXITCODE
