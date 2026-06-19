@echo off
chcp 65001 >nul
title NapCat QQ Bot

echo.
echo ============================================
echo   Mini-Drop x NapCat QQ Bot
echo ============================================
echo.

REM Find the NapCat shell directory (created by OneKey installer)
set SHELL_DIR=
for /d %%d in (NapCat.*.Shell) do set SHELL_DIR=%%d

if not "%SHELL_DIR%"=="" (
    echo Shell dir: %SHELL_DIR%
    echo.
    echo Starting NapCat with QQ from %SHELL_DIR% ...
    echo If QQ login window appears, please scan QR code.
    echo.
    cd /d "%SHELL_DIR%"
    if exist napcat.bat (
        call napcat.bat
    ) else (
        .\NapCatWinBootMain.exe
    )
    goto :end
)

REM Fallback: use bootmain
if exist bootmain\napcat.bat (
    echo Starting NapCat from bootmain ...
    cd bootmain
    call napcat.bat
    goto :end
)

echo [ERROR] NapCat shell not found.
echo Please run deploy\napcat\NapCatInstaller.exe first.
pause

:end
echo.
echo NapCat exited.
pause
