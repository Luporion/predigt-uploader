$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
[Console]::InputEncoding = [System.Text.UTF8Encoding]::new($false)
$OutputEncoding = [Console]::OutputEncoding

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Resolve-Path (Join-Path $ScriptDir "..")
$VenvDir = Join-Path $ProjectRoot ".venv"
$PythonExe = Join-Path $VenvDir "Scripts\python.exe"
$SrcDir = Join-Path $ProjectRoot "src"
$SetupScript = Join-Path $ScriptDir "setup-local.ps1"

function Write-UserError {
    param(
        [string]$Message,
        [string]$Hint
    )

    Write-Host ""
    Write-Host $Message -ForegroundColor Red
    Write-Host $Hint
    Write-Host ""
}

if (-not (Test-Path -LiteralPath $VenvDir -PathType Container)) {
    Write-UserError `
        "Die virtuelle Python-Umgebung .venv wurde nicht gefunden." `
        "Bitte zuerst PredigtUploader einrichten.cmd starten oder ausfuehren: $SetupScript"
    exit 1
}

if (-not (Test-Path -LiteralPath $PythonExe -PathType Leaf)) {
    Write-UserError `
        "In .venv wurde kein Python-Programm gefunden." `
        "Bitte die Einrichtung erneut starten: PredigtUploader einrichten.cmd"
    exit 1
}

Push-Location $ProjectRoot
try {
    if ($env:PYTHONPATH) {
        $env:PYTHONPATH = "$SrcDir;$env:PYTHONPATH"
    }
    else {
        $env:PYTHONPATH = $SrcDir
    }

    Write-Host "PredigtUploader Textual wird gestartet."
    Write-Host "Hinweis: Textual ist die experimentelle Oberflaeche. Der normale Wizard bleibt der produktive Standard."
    Write-Host ""
    & $PythonExe -m predigt_uploader tui
    exit $LASTEXITCODE
}
catch {
    Write-UserError `
        "Die Textual-Oberflaeche konnte nicht gestartet werden." `
        "Admin-Hinweis: $($_.Exception.Message)"
    exit 1
}
finally {
    Pop-Location
}
