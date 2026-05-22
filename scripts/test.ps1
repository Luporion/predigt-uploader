$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
[Console]::InputEncoding = [System.Text.UTF8Encoding]::new($false)
$OutputEncoding = [Console]::OutputEncoding

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Resolve-Path (Join-Path $ScriptDir "..")
$VenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"

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

function Initialize-TestFolder {
    param([string]$BasePath)

    if ([string]::IsNullOrWhiteSpace($BasePath)) {
        return $null
    }

    $RunDir = Join-Path $BasePath "run"
    $CacheDir = Join-Path $BasePath "cache"

    try {
        New-Item -ItemType Directory -Force -Path $BasePath | Out-Null

        foreach ($Folder in @($RunDir, $CacheDir)) {
            if (Test-Path -LiteralPath $Folder) {
                Remove-Item -LiteralPath $Folder -Recurse -Force
            }
            New-Item -ItemType Directory -Force -Path $Folder | Out-Null
            $ProbeFile = Join-Path $Folder "write-test.tmp"
            Set-Content -LiteralPath $ProbeFile -Value "ok" -Encoding UTF8
            Remove-Item -LiteralPath $ProbeFile -Force
        }

        return [pscustomobject]@{
            Base = $BasePath
            Run = $RunDir
            Cache = $CacheDir
        }
    }
    catch {
        Write-Host "Testordner nicht verwendbar: $BasePath" -ForegroundColor Yellow
        Write-Host "Admin-Hinweis: $($_.Exception.Message)"
        return $null
    }
}

$Candidates = @()
if (-not [string]::IsNullOrWhiteSpace($env:LOCALAPPDATA)) {
    $Candidates += Join-Path $env:LOCALAPPDATA "PredigtUploader\pytest"
}
if (-not [string]::IsNullOrWhiteSpace($env:TEMP)) {
    $Candidates += Join-Path $env:TEMP "PredigtUploader-pytest"
}

$TestFolder = $null
foreach ($Candidate in $Candidates) {
    $TestFolder = Initialize-TestFolder $Candidate
    if ($null -ne $TestFolder) {
        break
    }
}

if ($null -eq $TestFolder) {
    Write-UserError `
        "Die Tests konnten nicht gestartet werden, weil kein beschreibbarer Testordner gefunden wurde." `
        "Bitte pruefe die Windows-Berechtigungen fuer LOCALAPPDATA oder TEMP und versuche es erneut."
    exit 1
}

if (Test-Path -LiteralPath $VenvPython -PathType Leaf) {
    $PythonExe = $VenvPython
}
else {
    $PythonCommand = Get-Command python -ErrorAction SilentlyContinue
    if ($null -eq $PythonCommand) {
        Write-UserError `
            "Python wurde auf diesem Rechner nicht gefunden." `
            "Bitte Python 3.11 oder neuer installieren oder die lokale Umgebung mit setup-local.ps1 einrichten."
        exit 1
    }
    $PythonExe = $PythonCommand.Source
}

Push-Location $ProjectRoot
try {
    Write-Host "PredigtUploader Tests"
    Write-Host "====================="
    Write-Host "Testdaten: $($TestFolder.Run)"
    Write-Host "Pytest-Cache: $($TestFolder.Cache)"
    Write-Host ""

    & $PythonExe -m pytest --basetemp "$($TestFolder.Run)" -o "cache_dir=$($TestFolder.Cache)"
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}
