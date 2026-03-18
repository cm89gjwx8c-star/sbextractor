@echo off
setlocal

:: Get the current directory
set "APP_DIR=%~dp0"
set "APP_PATH=%APP_DIR%agent.py"
set "STARTUP_FOLDER=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
set "SHORTCUT_PATH=%STARTUP_FOLDER%\FortunaExtractor.vbs"

echo Setting up Fortuna Extractor background service...

:: Create a VBScript file that runs the app in the background (hidden console)
(
echo Set oShell = CreateObject^("WScript.Shell"^)
echo strArgs = "pythonw.exe """ ^& "%APP_PATH%" ^& """ --autostart"
echo oShell.Run strArgs, 0, false
) > "%SHORTCUT_PATH%"

echo.
echo Success! The extractor will now start automatically in the background when you log in.
echo You can find the icon in the system tray (near the clock).
echo.
echo To remove: Delete "%SHORTCUT_PATH%"
pause
