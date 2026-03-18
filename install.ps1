# Firebird Extractor One-Click Installer
# Run: powershell -ExecutionPolicy Bypass -File install.ps1

$ErrorActionPreference = "Stop"

$REPO_USER = "cm89gjwx8c-star"
$REPO_NAME = "sbextractor"
$INSTALL_DIR = "$env:LOCALAPPDATA\sbextractor"
$ZIP_URL = "https://github.com/$REPO_USER/$REPO_NAME/raw/main/release.zip"

Write-Host "--- Firebird Extractor Installer ---" -ForegroundColor Cyan

# 1. Prepare Directory
if (!(Test-Path $INSTALL_DIR)) {
    Write-Host "Creating installation directory: $INSTALL_DIR"
    New-Item -ItemType Directory -Path $INSTALL_DIR | Out-Null
}

# 2. Download Release
Write-Host "Downloading latest release from GitHub..." -ForegroundColor Yellow
$zipPath = Join-Path $env:TEMP "sbextractor_release.zip"
Invoke-WebRequest -Uri $ZIP_URL -OutFile $zipPath

# 3. Extract
Write-Host "Extracting files..." -ForegroundColor Yellow
if (Get-Command Expand-Archive -ErrorAction SilentlyContinue) {
    Expand-Archive -Path $zipPath -DestinationPath $INSTALL_DIR -Force
} else {
    # Fallback for older PowerShell versions (< 5.0)
    Write-Host "Using Shell.Application fallback for extraction..." -ForegroundColor Yellow
    $shell = New-Object -ComObject Shell.Application
    $zipFile = $shell.NameSpace($zipPath)
    $destFolder = $shell.NameSpace($INSTALL_DIR)
    $destFolder.CopyHere($zipFile.Items(), 16) # 16 = Respond "Yes to All" for overwrite
}
Remove-Item $zipPath

# 4. Initial Configuration (if missing)
$configPath = Join-Path $INSTALL_DIR "config.yaml"
if (!(Test-Path $configPath)) {
    Write-Host "Initializing configuration..." -ForegroundColor Yellow
    # Create basic config from template or default values
    $defaultConfig = @"
db:
  path: 'C:\softbilling\bill.gdb'
  user: 'SYSDBA'
  password: 'masterkey'
railway:
  url: 'https://vash-proekt.railway.app'
sync:
  interval_seconds: 60
security:
  pin_code: '0000'
"@
    Set-Content -Path $configPath -Value $defaultConfig
}

# 5. Set up Auto-start
Write-Host "Setting up Windows Startup..." -ForegroundColor Yellow
Set-Location $INSTALL_DIR
try {
    # Run the existing auto-start script
    cmd.exe /c "install_autostart.bat"
} catch {
    Write-Host "Warning: Could not set up autostart automatically." -ForegroundColor Red
}

# 6. Launch App (Hidden Mode)
Write-Host "Launching Firebird Extractor in background..." -ForegroundColor Green
$exePath = Join-Path $INSTALL_DIR "sbextractor.exe"
Start-Process -FilePath $exePath -ArgumentList "--autostart"

Write-Host "`nInstallation Complete! The extractor is now running in the system tray." -ForegroundColor Green
Write-Host "You can find the installation folder at: $INSTALL_DIR"
pause
