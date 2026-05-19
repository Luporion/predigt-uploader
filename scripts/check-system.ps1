$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
[Console]::InputEncoding = [System.Text.UTF8Encoding]::new($false)
$OutputEncoding = [Console]::OutputEncoding

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Resolve-Path (Join-Path $ScriptDir "..")
$VenvDir = Join-Path $ProjectRoot ".venv"
$VenvPython = Join-Path $VenvDir "Scripts\python.exe"
$ConfigPath = Join-Path $ProjectRoot "config.toml"

$Problems = New-Object System.Collections.Generic.List[string]

function Write-CheckOk {
    param([string]$Message)
    Write-Host "[OK] $Message" -ForegroundColor Green
}

function Write-CheckWarn {
    param([string]$Message)
    Write-Host "[FEHLT] $Message" -ForegroundColor Yellow
    $Problems.Add($Message) | Out-Null
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

function Test-AnyPython {
    if (Get-Command py -ErrorAction SilentlyContinue) {
        if (Test-PythonCandidate "py" @("-3.11")) {
            return $true
        }
    }
    if (Get-Command python -ErrorAction SilentlyContinue) {
        if (Test-PythonCandidate "python" @()) {
            return $true
        }
    }
    return $false
}

function Get-ConfiguredLosslessCutPath {
    if (-not (Test-Path -LiteralPath $ConfigPath -PathType Leaf)) {
        return ""
    }

    $Content = Get-Content -LiteralPath $ConfigPath -Raw
    $Match = [regex]::Match($Content, '(?m)^\s*losslesscut_path\s*=\s*"([^"]*)"\s*$')
    if (-not $Match.Success) {
        return ""
    }
    return $Match.Groups[1].Value.Replace("\\", "\")
}

Write-Host "PredigtUploader Systempruefung"
Write-Host "============================="
Write-Host ""

if (Test-AnyPython) {
    Write-CheckOk "Python 3.11 oder neuer ist verfuegbar."
}
else {
    Write-CheckWarn "Python 3.11 oder neuer wurde nicht gefunden. Bitte Python installieren und danach .\scripts\setup-local.ps1 ausfuehren."
}

if (Test-Path -LiteralPath $VenvDir -PathType Container) {
    Write-CheckOk "Die virtuelle Umgebung .venv existiert."
}
else {
    Write-CheckWarn "Die virtuelle Umgebung .venv fehlt. Bitte .\scripts\setup-local.ps1 ausfuehren."
}

if (Test-Path -LiteralPath $VenvPython -PathType Leaf) {
    Write-CheckOk "Python in .venv wurde gefunden."

    Push-Location $ProjectRoot
    try {
        & $VenvPython -m predigt_uploader --help *> $null
        if ($LASTEXITCODE -eq 0) {
            Write-CheckOk "Der Wizard ist startbar."
        }
        else {
            Write-CheckWarn "Der Wizard konnte nicht gestartet werden. Bitte .\scripts\setup-local.ps1 erneut ausfuehren."
        }
    }
    catch {
        Write-CheckWarn "Der Wizard konnte nicht gestartet werden. Admin-Hinweis: $($_.Exception.Message)"
    }
    finally {
        Pop-Location
    }

    try {
        & $VenvPython -c "from predigt_uploader.config import load_config; from predigt_uploader.mp3 import ffmpeg_available; raise SystemExit(0 if ffmpeg_available(load_config()) else 1)" *> $null
        if ($LASTEXITCODE -eq 0) {
            Write-CheckOk "FFmpeg ist fuer den Wizard verfuegbar."
        }
        else {
            Write-CheckWarn "FFmpeg wurde nicht gefunden. Ohne FFmpeg kann keine MP3 erstellt werden. Bitte FFmpeg installieren oder ffmpeg_path in config.toml setzen. Falls FFmpeg gerade installiert wurde, ein neues PowerShell-Fenster oeffnen und diese Pruefung erneut starten."
        }
    }
    catch {
        Write-CheckWarn "FFmpeg konnte nicht geprueft werden. Admin-Hinweis: $($_.Exception.Message)"
    }
}
else {
    Write-CheckWarn "In .venv wurde kein python.exe gefunden. Bitte .\scripts\setup-local.ps1 ausfuehren."
}

$LosslessCutPath = Get-ConfiguredLosslessCutPath
if ([string]::IsNullOrWhiteSpace($LosslessCutPath)) {
    Write-Host "[INFO] In config.toml ist kein losslesscut_path gesetzt. Der Wizard versucht spaeter PATH/App-Alias oder fragt nach." -ForegroundColor Cyan
}
else {
    if ((Test-Path -LiteralPath $LosslessCutPath -PathType Leaf) -and ($LosslessCutPath.ToLowerInvariant().EndsWith(".exe"))) {
        Write-CheckOk "Der konfigurierte LosslessCut-Pfad zeigt auf eine EXE-Datei."
    }
    else {
        Write-CheckWarn "Der konfigurierte losslesscut_path wurde nicht gefunden oder ist keine EXE-Datei: $LosslessCutPath"
    }
}

Write-Host ""
if ($Problems.Count -eq 0) {
    Write-Host "Systempruefung abgeschlossen: Alles Wichtige sieht gut aus." -ForegroundColor Green
    exit 0
}

Write-Host "Systempruefung abgeschlossen: Es fehlen noch Punkte." -ForegroundColor Yellow
Write-Host "Bitte die Hinweise oben abarbeiten und die Pruefung danach erneut starten."
exit 1
