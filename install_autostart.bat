@echo off
setlocal

:: Get the current directory and determine the target app
set "APP_DIR=%~dp0"
if exist "%APP_DIR%sbextractor.exe" (
    set "TARGET_PATH=%APP_DIR%sbextractor.exe"
) else (
    set "TARGET_PATH=%APP_DIR%agent.py"
)

echo --- Fortuna Extractor Autostart Setup ---
echo App Path: %TARGET_PATH%

:: Determine if we need pythonw or if it's an exe
if "%TARGET_PATH:~-4%"==".exe" (
    set "CMD_LINE=\"%TARGET_PATH%\" --autostart"
) else (
    set "CMD_LINE=pythonw.exe \"%TARGET_PATH%\" --autostart"
)

echo Setting up Registry Run key...
reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\Run" /v "FortunaExtractor" /t REG_SZ /d "%CMD_LINE%" /f

if %ERRORLEVEL% EQU 0 (
    echo.
    echo Success! The extractor will now start automatically in the background when you log in.
    echo.
) else (
    echo.
    echo Error: Failed to update registry. Please try running this script as Administrator.
    echo.
)

pause
