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

function Test-FFmpegInPath {
    return $null -ne (Get-Command ffmpeg -ErrorAction SilentlyContinue)
}

function Show-ManualFFmpegHelp {
    Write-Host ""
    Write-Host "FFmpeg wird fuer die MP3-Erzeugung benoetigt." -ForegroundColor Yellow
    Write-Host "Ohne FFmpeg kann der Wizard die MP4 vorbereiten, aber keine MP3 erstellen."
    Write-Host ""
    Write-Host "Manuelle Installation:"
    Write-Host "1. FFmpeg installieren, zum Beispiel ueber winget oder von der offiziellen FFmpeg-Webseite."
    Write-Host "2. Danach ein neues PowerShell-Fenster oeffnen."
    Write-Host "3. .\scripts\check-system.ps1 erneut starten."
    Write-Host ""
    Write-Host "Alternative fuer Admins: In config.toml unter [paths] ffmpeg_path auf die ffmpeg.exe setzen."
}

function Confirm-Yes {
    param([string]$Prompt)
    $Answer = Read-Host "$Prompt [j/N]"
    return $Answer.Trim().ToLowerInvariant() -in @("j", "ja", "y", "yes")
}

function Check-Or-Offer-FFmpegInstall {
    Write-Step "FFmpeg wird geprueft..."
    if (Test-FFmpegInPath) {
        Write-Host "FFmpeg ist im PATH verfuegbar." -ForegroundColor Green
        return
    }

    Write-Host "FFmpeg wurde nicht gefunden." -ForegroundColor Yellow
    Write-Host "FFmpeg ist noetig, damit der PredigtUploader aus der MP4 eine MP3 erstellen kann."

    if (Get-Command winget -ErrorAction SilentlyContinue) {
        Write-Host ""
        Write-Host "Auf diesem Rechner ist winget verfuegbar."
        Write-Host "Damit kann FFmpeg automatisch installiert werden. Windows zeigt dabei ggf. eigene Rueckfragen an."
        if (Confirm-Yes "FFmpeg jetzt mit winget installieren?") {
            winget install --id Gyan.FFmpeg -e
            if ($LASTEXITCODE -eq 0) {
                Write-Host ""
                Write-Host "FFmpeg-Installation wurde gestartet oder abgeschlossen." -ForegroundColor Green
                Write-Host "Wichtig: Oeffne danach ein neues PowerShell-Fenster und starte .\scripts\check-system.ps1 erneut."
                return
            }
            Write-Host ""
            Write-Host "Die winget-Installation von FFmpeg war nicht erfolgreich." -ForegroundColor Yellow
            Write-Host "Admin-Hinweis: winget install --id Gyan.FFmpeg -e Exit-Code $LASTEXITCODE"
        }
        else {
            Write-Host "FFmpeg wird jetzt nicht automatisch installiert."
        }
    }
    else {
        Write-Host "winget wurde auf diesem Rechner nicht gefunden. Eine automatische Installation ist hier nicht moeglich."
    }

    Show-ManualFFmpegHelp
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
    Check-Or-Offer-FFmpegInstall
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
