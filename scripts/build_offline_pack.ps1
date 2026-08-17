#requires -Version 5.1
<#
.SYNOPSIS
  Build an offline Windows pack: EXE + bundled Tesseract, no pip/internet on the target PC.
#>
param(
    [string]$Version = "0.3.0"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
if (-not (Test-Path (Join-Path $Root "launch.py"))) {
    $Root = Get-Location | Select-Object -ExpandProperty Path
}

Set-Location $Root
$Vendor = Join-Path $Root "vendor"
$TessDir = Join-Path $Vendor "tesseract"
$DownloadDir = Join-Path $Vendor "downloads"
$DistDir = Join-Path $Root "dist\SideBendingRestartAgent"
$PackName = "SideBendingRestartAgent-$Version-windows-x64"
$PackDir = Join-Path $Root "dist\$PackName"
$ZipPath = Join-Path $Root "dist\$PackName.zip"
$TessUrl = "https://github.com/tesseract-ocr/tesseract/releases/download/5.5.3/tesseract-ocr-w64-setup-5.5.3.20260724.exe"
$TessSetup = Join-Path $DownloadDir "tesseract-ocr-w64-setup-5.5.3.20260724.exe"

New-Item -ItemType Directory -Force -Path $Vendor, $DownloadDir | Out-Null

function Test-TesseractTree([string]$Path) {
    return (Test-Path (Join-Path $Path "tesseract.exe")) -and (Test-Path (Join-Path $Path "tessdata"))
}

function Copy-SlimTesseract([string]$From, [string]$To) {
    if (-not (Test-Path (Join-Path $From "tesseract.exe"))) {
        throw "tesseract.exe missing in $From"
    }
    if (Test-Path $To) {
        Remove-Item -Recurse -Force $To
    }
    New-Item -ItemType Directory -Force -Path $To | Out-Null
    Copy-Item (Join-Path $From "tesseract.exe") $To
    Get-ChildItem $From -Filter "*.dll" | Copy-Item -Destination $To
    $tessdataTo = Join-Path $To "tessdata"
    New-Item -ItemType Directory -Force -Path $tessdataTo | Out-Null
    Copy-Item (Join-Path $From "tessdata\eng.traineddata") $tessdataTo
    $osd = Join-Path $From "tessdata\osd.traineddata"
    if (Test-Path $osd) {
        Copy-Item $osd $tessdataTo
    }
}

function Install-BundledTesseract {
    if (Test-TesseractTree $TessDir) {
        Write-Host "Using existing vendor tesseract at $TessDir"
        return
    }

    $programFiles = @(
        "${env:ProgramFiles}\Tesseract-OCR",
        "${env:ProgramFiles(x86)}\Tesseract-OCR"
    )
    foreach ($pf in $programFiles) {
        if (Test-TesseractTree $pf) {
            Write-Host "Copying installed Tesseract from $pf"
            Copy-SlimTesseract $pf $TessDir
            return
        }
    }

    if (-not (Test-Path $TessSetup)) {
        Write-Host "Downloading Tesseract 5.5.3 installer..."
        Invoke-WebRequest -Uri $TessUrl -OutFile $TessSetup -UseBasicParsing
    }

    $sevenZip = @(
        "${env:ProgramFiles}\7-Zip\7z.exe",
        "${env:ProgramFiles(x86)}\7-Zip\7z.exe"
    ) | Where-Object { Test-Path $_ } | Select-Object -First 1

    if ($sevenZip) {
        Write-Host "Extracting installer with 7-Zip..."
        $extractTmp = Join-Path $DownloadDir "tess_extract"
        if (Test-Path $extractTmp) {
            Remove-Item -Recurse -Force $extractTmp
        }
        New-Item -ItemType Directory -Force -Path $extractTmp | Out-Null
        & $sevenZip x "-o$extractTmp" -y $TessSetup | Out-Null
        if (Test-TesseractTree $extractTmp) {
            Copy-SlimTesseract $extractTmp $TessDir
            return
        }
        $nested = Get-ChildItem -Path $extractTmp -Recurse -Filter "tesseract.exe" -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($nested) {
            Copy-SlimTesseract $nested.Directory.FullName $TessDir
            return
        }
    }

    Write-Host "Silent-installing Tesseract into $TessDir ..."
    $abs = [System.IO.Path]::GetFullPath($TessDir)
    New-Item -ItemType Directory -Force -Path $abs | Out-Null
    $proc = Start-Process -FilePath $TessSetup -ArgumentList "/S", "/D=$abs" -Wait -PassThru
    if ($proc.ExitCode -ne 0 -and $proc.ExitCode -ne $null) {
        Write-Warning "NSIS installer exit code $($proc.ExitCode)"
    }
    if (-not (Test-TesseractTree $TessDir)) {
        throw "Failed to produce bundled tesseract.exe. Install 7-Zip or Tesseract, then re-run."
    }
}

Install-BundledTesseract
if (-not (Test-Path (Join-Path $TessDir "tessdata\eng.traineddata"))) {
    throw "eng.traineddata missing under $TessDir\tessdata"
}

Write-Host "Creating isolated pack venv..."
$VenvDir = Join-Path $Root ".venv-pack"
$VenvPython = Join-Path $VenvDir "Scripts\python.exe"
if (-not (Test-Path $VenvPython)) {
    python -m venv $VenvDir
}
& $VenvPython -m pip install -q --upgrade pip
& $VenvPython -m pip install -q -r (Join-Path $Root "requirements.txt") -r (Join-Path $Root "requirements-build.txt")

Write-Host "Running PyInstaller with pack venv..."
& $VenvPython -m PyInstaller --noconfirm --clean (Join-Path $Root "build_exe.spec")

if (-not (Test-Path (Join-Path $DistDir "SideBendingRestartAgent.exe"))) {
    throw "PyInstaller did not produce SideBendingRestartAgent.exe"
}

Copy-SlimTesseract $TessDir (Join-Path $DistDir "tesseract")
Copy-Item (Join-Path $Root "config.yaml") (Join-Path $DistDir "config.yaml") -Force
Copy-Item (Join-Path $Root "README.md") (Join-Path $DistDir "README.md") -Force
Set-Content -Path (Join-Path $DistDir "VERSION.txt") -Value $Version -Encoding ascii
Set-Content -Path (Join-Path $DistDir "RUN.bat") -Value @"
@echo off
cd /d "%~dp0"
start "" "%~dp0SideBendingRestartAgent.exe"
"@ -Encoding ascii
Set-Content -Path (Join-Path $DistDir "OFFLINE.txt") -Value @"
Offline pack v$Version
Unzip this folder onto the line PC. No Python, pip, Tesseract, or internet is required.
1. Double-click RUN.bat or SideBendingRestartAgent.exe
2. Calibrate ROI and click points
3. Dry-run recovery before live clicks
OCR: Windows.Media.Ocr when the English OCR pack exists, otherwise bundled Tesseract 5.5.3.
Config: config.yaml next to the EXE (writable).
Logs: logs\agent.log and logs\events.jsonl
"@ -Encoding ascii

if (Test-Path $PackDir) {
    Remove-Item -Recurse -Force $PackDir
}
New-Item -ItemType Directory -Force -Path (Split-Path $PackDir) | Out-Null
Copy-Item $DistDir $PackDir -Recurse

if (Test-Path $ZipPath) {
    Remove-Item -Force $ZipPath
}
Add-Type -AssemblyName System.IO.Compression.FileSystem
[System.IO.Compression.ZipFile]::CreateFromDirectory($PackDir, $ZipPath)

Write-Host "Pack ready:"
Write-Host "  $PackDir"
Write-Host "  $ZipPath"
Get-Item $ZipPath | Select-Object FullName, Length
