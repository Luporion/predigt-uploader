$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
[Console]::InputEncoding = [System.Text.UTF8Encoding]::new($false)
$OutputEncoding = [Console]::OutputEncoding

$Version = "0.1.8"
$ReleaseName = "predigt-uploader-v$Version-textual-metadata-preview"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Resolve-Path (Join-Path $ScriptDir "..")
$DistDir = Join-Path $ProjectRoot "dist"
$StagingDir = Join-Path $DistDir $ReleaseName
$ZipPath = Join-Path $DistDir "$ReleaseName.zip"

$ReleaseItems = @(
    "src",
    "scripts",
    "docs\install-v1-5.md",
    "docs\manual-test-v1-5.md",
    "README.md",
    "pyproject.toml",
    "config.example.toml",
    "PredigtUploader starten.cmd",
    "PredigtUploader einrichten.cmd",
    "PredigtUploader Systemcheck.cmd",
    "Tests ausfuehren.cmd"
)

$ExcludedNames = @(
    ".git",
    ".venv",
    "logs",
    "dist",
    "build",
    "__pycache__",
    ".pytest_cache",
    ".pytest-tmp",
    "test-extract",
    "Windows PowerShell.txt",
    "config.toml"
)

$ExcludedPatterns = @(
    "*.egg-info",
    "*.pyc"
)

function Write-Step {
    param([string]$Message)
    Write-Host $Message -ForegroundColor Cyan
}

function Copy-ReleaseItem {
    param([string]$RelativePath)

    $Source = Join-Path $ProjectRoot $RelativePath
    if (-not (Test-Path -LiteralPath $Source)) {
        throw "Release-Datei fehlt: $RelativePath"
    }

    $Destination = Join-Path $StagingDir $RelativePath
    $DestinationParent = Split-Path -Parent $Destination
    New-Item -ItemType Directory -Force -Path $DestinationParent | Out-Null
    Copy-Item -LiteralPath $Source -Destination $Destination -Recurse -Force
}

function Remove-ExcludedFromStaging {
    foreach ($Name in $ExcludedNames) {
        Get-ChildItem -LiteralPath $StagingDir -Recurse -Force -ErrorAction SilentlyContinue |
            Where-Object { $_.Name -eq $Name } |
            Remove-Item -Recurse -Force
    }

    foreach ($Pattern in $ExcludedPatterns) {
        Get-ChildItem -LiteralPath $StagingDir -Recurse -Force -ErrorAction SilentlyContinue |
            Where-Object { $_.Name -like $Pattern } |
            Remove-Item -Recurse -Force
    }
}

Write-Host "PredigtUploader Release-ZIP erstellen"
Write-Host "====================================="

New-Item -ItemType Directory -Force -Path $DistDir | Out-Null

if (Test-Path -LiteralPath $StagingDir) {
    Remove-Item -LiteralPath $StagingDir -Recurse -Force
}
if (Test-Path -LiteralPath $ZipPath) {
    Remove-Item -LiteralPath $ZipPath -Force
}

New-Item -ItemType Directory -Force -Path $StagingDir | Out-Null

foreach ($Item in $ReleaseItems) {
    Write-Step "Kopiere: $Item"
    Copy-ReleaseItem $Item
}

Remove-ExcludedFromStaging

Write-Step "Erstelle ZIP: $ZipPath"
Compress-Archive -Path (Join-Path $StagingDir "*") -DestinationPath $ZipPath -Force

Remove-Item -LiteralPath $StagingDir -Recurse -Force

Write-Host ""
Write-Host "Release-ZIP wurde erstellt:" -ForegroundColor Green
Write-Host $ZipPath
