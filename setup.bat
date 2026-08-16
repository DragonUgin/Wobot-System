@echo off
title Claw // Wubot Extreme Challenge - Setup
set "PDIR=%~dp0"

echo ============================================
echo   Claw // Wubot Extreme Challenge - Setup
echo ============================================
echo.

REM ---- 1. Python dependencies (NoneBot2 / FastAPI are MIT-licensed libs) ----
echo [1/2] Installing Python dependencies from Claw\requirements.txt ...
"%PDIR%python-embed\python.exe" -m pip install -r "%PDIR%Claw\requirements.txt"
if errorlevel 1 (
    echo   pip install failed. Check that python-embed is present and has pip.
    pause
    exit /b 1
)
echo   Python dependencies ready.
echo.

REM ---- 2. NapCat (third-party, RESTRICTED REDISTRIBUTION license) ----
echo [2/2] NapCat (QQ protocol client) is NOT installed automatically.
echo   - NapCat is released under a RESTRICTED REDISTRIBUTION license.
echo   - You MUST download the official release yourself (do not redistribute it).
echo   - Download: https://github.com/NapNeko/NapCatQQ/releases
echo   - Extract it into the 'napcat' folder next to this file.
echo   - License terms: personal / non-commercial use only;
echo       you may NOT redistribute, re-publish modified versions, or use commercially.
echo.

echo Setup complete.
echo   Next:
echo     1. Copy Claw\.env.example to Claw\.env and fill in your QQ / group IDs.
echo     2. Double-click start.bat to launch the bot + NapCat.
echo.
pause
