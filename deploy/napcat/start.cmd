@echo off
chcp 65001 >nul
title Mini-Drop QQ Bot - NapCat

echo.
echo ============================================
echo   Mini-Drop QQ Bot - Starting...
echo ============================================
echo.
echo This will open NapCat + QQ login window.
echo Please scan QR code or login to your QQ bot account.
echo.
echo After login, OneBot HTTP API will start at:
echo   http://localhost:5700
echo.
echo Keep this window open while using the bot.
echo ============================================
echo.

REM Find NapCat Shell directory
set SHELL_DIR=
for /d %%d in (NapCat.*.Shell) do set SHELL_DIR=%%d

if not "%SHELL_DIR%"=="" (
    echo Found: %SHELL_DIR%
    cd /d "%SHELL_DIR%"
) else (
    if exist bootmain (
        echo Using bootmain
        cd bootmain
    ) else (
        echo [ERROR] NapCat not found. Run NapCatInstaller.exe first.
        pause
        exit /b 1
    )
)

if exist napcat.bat (
    echo Starting NapCat...
    call napcat.bat
) else (
    .\NapCatWinBootMain.exe
)

echo.
echo NapCat exited.
pause
