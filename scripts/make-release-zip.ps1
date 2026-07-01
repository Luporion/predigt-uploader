param(
    [string]$ReleaseTag = "",
    [string]$ReleaseName = ""
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
[Console]::InputEncoding = [System.Text.UTF8Encoding]::new($false)
$OutputEncoding = [Console]::OutputEncoding

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Resolve-Path (Join-Path $ScriptDir "..")
$DistDir = Join-Path $ProjectRoot "dist"

$ReleaseItems = @(
    "src",
    "scripts",
    "docs\install-v1-5.md",
    "docs\manual-test-v1-5.md",
    "README.md",
    "pyproject.toml",
    "config.example.toml",
    "PredigtUploader starten.cmd",
    "PredigtUploader Textual starten.cmd",
    "PredigtUploader einrichten.cmd",
    "PredigtUploader Systemcheck.cmd"
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
    "*.pyc",
    "*.lnk"
)

function Write-Step {
    param([string]$Message)
    Write-Host $Message -ForegroundColor Cyan
}

function Get-PyprojectVersion {
    $PyprojectPath = Join-Path $ProjectRoot "pyproject.toml"
    if (-not (Test-Path -LiteralPath $PyprojectPath -PathType Leaf)) {
        return "0.0.0"
    }

    $Content = Get-Content -LiteralPath $PyprojectPath -Raw
    $Match = [regex]::Match($Content, '(?m)^\s*version\s*=\s*"([^"]+)"\s*$')
    if ($Match.Success) {
        return $Match.Groups[1].Value
    }
    return "0.0.0"
}

function Get-HeadReleaseTag {
    try {
        $Tags = git -C $ProjectRoot tag --points-at HEAD 2>$null
        if ($LASTEXITCODE -ne 0 -or $null -eq $Tags) {
            return ""
        }

        $MatchingTags = @($Tags | Where-Object { $_ -match '^v\d+\.\d+\.\d+' } | Sort-Object)
        if ($MatchingTags.Count -gt 0) {
            return $MatchingTags[0]
        }

        $AllTags = @($Tags | Sort-Object)
        if ($AllTags.Count -gt 0) {
            return $AllTags[0]
        }
    }
    catch {
        return ""
    }
    return ""
}

function Resolve-ReleaseName {
    if (-not [string]::IsNullOrWhiteSpace($ReleaseName)) {
        return $ReleaseName.Trim()
    }

    if (-not [string]::IsNullOrWhiteSpace($ReleaseTag)) {
        return "predigt-uploader-$($ReleaseTag.Trim())"
    }

    $HeadTag = Get-HeadReleaseTag
    if (-not [string]::IsNullOrWhiteSpace($HeadTag)) {
        return "predigt-uploader-$HeadTag"
    }

    $Version = Get-PyprojectVersion
    return "predigt-uploader-v$Version-local"
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

$ResolvedReleaseName = Resolve-ReleaseName
$StagingDir = Join-Path $DistDir $ResolvedReleaseName
$ZipPath = Join-Path $DistDir "$ResolvedReleaseName.zip"

Write-Host "Release-Name: $ResolvedReleaseName"
Write-Host "ZIP-Ziel: $ZipPath"
Write-Host ""

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
