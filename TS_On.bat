@echo off
setlocal EnableExtensions
echo =========================================
echo   Enable Test Signing
echo =========================================
echo.

net session >nul 2>&1
if %errorlevel% neq 0 (
    echo Requesting administrator privileges...
    powershell -NoProfile -Command "Start-Process '%~f0' -Verb RunAs -ArgumentList '/c \"%~f0\"' -Wait"
    exit /b
)

echo Setting testsigning on...
bcdedit /set testsigning on
if %errorlevel% neq 0 (
    echo FAILED to set testsigning
    pause
    exit /b
)

echo.
echo Test Signing ENABLED.
echo NEXT STEP: REBOOT your PC.
echo After reboot, "Test Mode" watermark on desktop is NORMAL.
echo Then double-click Play.bat to launch the game.
echo.
pause