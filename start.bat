@echo off
title Wobot-Portable

set "PDIR=%~dp0"

echo ========================================
echo   Wobot // Extreme Challenge
echo   Portable v3.0
echo ========================================
echo.

echo [1/2] Starting Bot...
start "Wobot" /D "%PDIR%Claw" "%PDIR%python-embed\python.exe" bot.py

echo Waiting 8 seconds for Bot...
timeout /t 8 /nobreak >nul

echo [2/2] Starting NapCat...
REM 设置 conhost 下标题为 "NapCat" 的窗口字体为 Consolas（支持 Unicode 块字符，二维码不乱码）
reg add "HKCU\Console\NapCat" /v FaceName /t REG_SZ /d Consolas /f >nul 2>&1
reg add "HKCU\Console\NapCat" /v FontFamily /t REG_DWORD /d 54 /f >nul 2>&1
reg add "HKCU\Console\NapCat" /v FontSize /t REG_DWORD /d 0x000e0000 /f >nul 2>&1
reg add "HKCU\Console\NapCat" /v FontWeight /t REG_DWORD /d 400 /f >nul 2>&1
where wt >nul 2>&1
if %errorlevel% equ 0 (
    echo   [Windows Terminal] - best QR display
    start "" wt -d "%PDIR%napcat" --title "NapCat - QQ Bot" "%PDIR%napcat\napcat.bat"
) else (
    echo   [CMD + Consolas font]
    start "NapCat" /D "%PDIR%napcat" napcat.bat
)

timeout /t 3 /nobreak >nul
start http://127.0.0.1:8080

echo.
echo ========================================
echo   Done!
echo.
echo   Web UI    : http://127.0.0.1:8080
echo   NapCat    : http://127.0.0.1:6099
echo.
echo   群号 / QQ / Token 等配置均在 Claw\.env（已忽略，不入库）
echo ========================================
echo.
pause
