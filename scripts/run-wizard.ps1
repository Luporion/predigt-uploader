$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Resolve-Path (Join-Path $ScriptDir "..")
$VenvDir = Join-Path $ProjectRoot ".venv"
$PythonExe = Join-Path $VenvDir "Scripts\python.exe"
$SrcDir = Join-Path $ProjectRoot "src"

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
    $HasPython = [bool](Get-Command py -ErrorAction SilentlyContinue) -or [bool](Get-Command python -ErrorAction SilentlyContinue)

    Write-UserError `
        "Die virtuelle Python-Umgebung .venv wurde nicht gefunden." `
        "Bitte im Projektordner zuerst ausführen: py -3.11 -m venv .venv"

    if (-not $HasPython) {
        Write-UserError `
            "Python wurde auf diesem Rechner nicht gefunden." `
            "Bitte Python 3.11 oder neuer installieren und danach die .venv neu erstellen."
    }

    exit 1
}

if (-not (Test-Path -LiteralPath $PythonExe -PathType Leaf)) {
    Write-UserError `
        "In .venv wurde kein Python-Programm gefunden." `
        "Bitte die virtuelle Umgebung neu erstellen: py -3.11 -m venv .venv"
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

    & $PythonExe -m predigt_uploader wizard @args
    exit $LASTEXITCODE
}
catch {
    Write-UserError `
        "Der Wizard konnte nicht gestartet werden." `
        "Admin-Hinweis: $($_.Exception.Message)"
    exit 1
}
finally {
    Pop-Location
}
