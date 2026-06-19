# Mini-Drop NapCat QQ Bot Setup
# Usage: powershell -ExecutionPolicy Bypass -File setup.ps1
# Encoding: UTF-8 with BOM

param(
    [string]$InstallDir = "$PSScriptRoot"
)

$ErrorActionPreference = "Stop"
$NAP_VER = "v4.18.6"
$NAP_URL = "https://github.com/NapNeko/NapCatQQ/releases/download/$NAP_VER/NapCat.Shell.Windows.OneKey.zip"
$ZIP_FILE = Join-Path $InstallDir "NapCat.OneKey.zip"

Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  Mini-Drop x NapCat QQ Bot Setup" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

# Step 1: Download
Write-Host "[1/3] Downloading NapCat $NAP_VER ..." -ForegroundColor Yellow
if (Test-Path $ZIP_FILE) {
    Write-Host "  Already downloaded, skipping" -ForegroundColor Green
} else {
    try {
        [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.SecurityProtocolType]::Tls12
        Invoke-WebRequest -Uri $NAP_URL -OutFile $ZIP_FILE -TimeoutSec 180
        Write-Host "  Done: $ZIP_FILE" -ForegroundColor Green
    } catch {
        Write-Host "  Download failed!" -ForegroundColor Red
        Write-Host "  Manual download: $NAP_URL" -ForegroundColor Gray
        Write-Host "  Extract to: $InstallDir" -ForegroundColor Gray
        Read-Host "Press Enter to exit"
        exit 1
    }
}

# Step 2: Extract
Write-Host "[2/3] Extracting ..." -ForegroundColor Yellow
try {
    Expand-Archive -Path $ZIP_FILE -DestinationPath $InstallDir -Force
    Write-Host "  Done" -ForegroundColor Green
} catch {
    Write-Host "  Extract failed! Please unzip $ZIP_FILE manually to $InstallDir" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

# Step 3: Generate launcher
Write-Host "[3/3] Generating launcher scripts ..." -ForegroundColor Yellow

$startCmd = @'
@echo off
chcp 65001 >nul
title NapCat QQ Bot
echo.
echo ============================================
echo   NapCat QQ Bot - Starting...
echo ============================================
echo.
echo If QQ login window appears, scan QR code to login.
echo After login, NapCat runs in background.
echo.
echo OneBot HTTP API: http://localhost:5700
echo.
echo Press Ctrl+C to stop the bot.
echo ============================================
echo.
if exist bootmain\napcat.bat (
    cd bootmain
    call napcat.bat
) else (
    echo [ERROR] bootmain\napcat.bat not found
    pause
)
'@

$quickCmd = @'
@echo off
chcp 65001 >nul
title NapCat QQ Bot (Quick)
if exist bootmain\napcat.quick.bat (
    cd bootmain
    call napcat.quick.bat
) else (
    echo [ERROR] bootmain\napcat.quick.bat not found
    pause
)
'@

[System.IO.File]::WriteAllText((Join-Path $InstallDir "start-qq.cmd"), $startCmd, [System.Text.UTF8Encoding]::new($true))
[System.IO.File]::WriteAllText((Join-Path $InstallDir "start-qq-quick.cmd"), $quickCmd, [System.Text.UTF8Encoding]::new($true))

Write-Host "  start-qq.cmd created" -ForegroundColor Green
Write-Host "  start-qq-quick.cmd created" -ForegroundColor Green

Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  Setup complete!" -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Next steps:" -ForegroundColor White
Write-Host ""
Write-Host "  1. Run: deploy\napcat\start-qq.cmd" -ForegroundColor Yellow
Write-Host "  2. Scan QR code to login QQ" -ForegroundColor Yellow
Write-Host "  3. Get your QQ group ID (right-click group -> info -> copy number)" -ForegroundColor Yellow
Write-Host "  4. Add to Mini-Drop .env:" -ForegroundColor Yellow
Write-Host ""
Write-Host "     MINI_DROP_CHATOPS_ENABLED=1" -ForegroundColor Gray
Write-Host "     MINI_DROP_CHATOPS_PROVIDER=qqbot" -ForegroundColor Gray
Write-Host "     MINI_DROP_CHATOPS_WEBHOOK_URL=http://localhost:5700" -ForegroundColor Gray
Write-Host "     MINI_DROP_QQBOT_TARGET_TYPE=group" -ForegroundColor Gray
Write-Host "     MINI_DROP_QQBOT_TARGET_ID=YOUR_GROUP_ID" -ForegroundColor Gray
Write-Host ""
Write-Host "  5. Start Mini-Drop and test: micro-drop chatops-test" -ForegroundColor Yellow
Write-Host ""
Write-Host "  Full guide: deploy/napcat/README.md" -ForegroundColor Gray
Write-Host ""
Read-Host "Press Enter to exit"
