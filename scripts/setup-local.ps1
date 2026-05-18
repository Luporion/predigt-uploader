param(
    [switch]$IncludeDev
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
[Console]::InputEncoding = [System.Text.UTF8Encoding]::new($false)
$OutputEncoding = [Console]::OutputEncoding

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Resolve-Path (Join-Path $ScriptDir "..")
$VenvDir = Join-Path $ProjectRoot ".venv"
$VenvPython = Join-Path $VenvDir "Scripts\python.exe"

function Write-Step {
    param([string]$Message)
    Write-Host ""
    Write-Host $Message -ForegroundColor Cyan
}

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

function Test-PythonCandidate {
    param(
        [string]$Command,
        [string[]]$Arguments
    )

    try {
        & $Command @Arguments -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)" *> $null
        return ($LASTEXITCODE -eq 0)
    }
    catch {
        return $false
    }
}

function Get-UsablePython {
    if (Get-Command py -ErrorAction SilentlyContinue) {
        if (Test-PythonCandidate "py" @("-3.11")) {
            return @{ Command = "py"; Arguments = @("-3.11") }
        }
    }

    if (Get-Command python -ErrorAction SilentlyContinue) {
        if (Test-PythonCandidate "python" @()) {
            return @{ Command = "python"; Arguments = @() }
        }
    }

    return $null
}

Write-Host "PredigtUploader lokale Einrichtung"
Write-Host "=================================="

$Python = Get-UsablePython
if ($null -eq $Python) {
    Write-UserError `
        "Python 3.11 oder neuer wurde nicht gefunden." `
        "Bitte Python von python.org installieren. Wichtig: Beim Installieren 'Add Python to PATH' aktivieren."
    exit 1
}

Push-Location $ProjectRoot
try {
    if (-not (Test-Path -LiteralPath $VenvDir -PathType Container)) {
        Write-Step "Virtuelle Python-Umgebung .venv wird erstellt..."
        & $Python.Command @($Python.Arguments) -m venv $VenvDir
        if ($LASTEXITCODE -ne 0) {
            Write-UserError `
                "Die virtuelle Python-Umgebung konnte nicht erstellt werden." `
                "Admin-Hinweis: python -m venv .venv ist fehlgeschlagen."
            exit 1
        }
    }
    else {
        Write-Step "Virtuelle Python-Umgebung .venv ist bereits vorhanden."
    }

    if (-not (Test-Path -LiteralPath $VenvPython -PathType Leaf)) {
        Write-UserError `
            "In .venv wurde kein Python-Programm gefunden." `
            "Bitte den Ordner .venv loeschen und dieses Setup erneut ausfuehren."
        exit 1
    }

    Write-Step "pip wird aktualisiert..."
    & $VenvPython -m pip install --upgrade pip
    if ($LASTEXITCODE -ne 0) {
        Write-UserError `
            "pip konnte nicht aktualisiert werden." `
            "Bitte Internetverbindung pruefen und das Setup erneut starten."
        exit 1
    }

    $InstallTarget = "."
    if ($IncludeDev) {
        $InstallTarget = ".[dev]"
    }

    Write-Step "PredigtUploader und Abhaengigkeiten werden installiert..."
    & $VenvPython -m pip install -e $InstallTarget
    if ($LASTEXITCODE -ne 0) {
        Write-UserError `
            "Die Python-Abhaengigkeiten konnten nicht installiert werden." `
            "Bitte Internetverbindung pruefen. Admin-Hinweis: python -m pip install -e $InstallTarget ist fehlgeschlagen."
        exit 1
    }

    Write-Host ""
    Write-Host "Einrichtung abgeschlossen." -ForegroundColor Green
    Write-Host "Naechster Schritt:"
    Write-Host ".\scripts\check-system.ps1"
}
catch {
    Write-UserError `
        "Die lokale Einrichtung wurde unerwartet abgebrochen." `
        "Admin-Hinweis: $($_.Exception.Message)"
    exit 1
}
finally {
    Pop-Location
}
