@echo off
setlocal EnableExtensions
echo =========================================
echo   Disable Test Signing
echo =========================================
echo.

net session >nul 2>&1
if %errorlevel% neq 0 (
    echo Requesting administrator privileges...
    powershell -NoProfile -Command "Start-Process '%~f0' -Verb RunAs -ArgumentList '/c \"%~f0\"' -Wait"
    exit /b
)

echo Setting testsigning off...
bcdedit /set testsigning off
if %errorlevel% neq 0 (
    echo FAILED to set testsigning
    pause
    exit /b
)

echo.
echo Test Signing DISABLED.
echo NEXT STEP: REBOOT your PC.
echo.
pause