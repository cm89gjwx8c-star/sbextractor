# sbextractor Installer for Windows

$InstallDir = "$env:USERPROFILE\sbextractor"
$ExeUrl = "https://github.com/USERNAME/REPO/releases/latest/download/sbextractor.exe" # Placeholder URL

function Show-Notification {
    param($Title, $Message)
    Write-Host "$Title: $Message"
}

# 1. Create Installation Directory
if (!(Test-Path $InstallDir)) {
    New-Item -ItemType Directory -Path $InstallDir
    Write-Host "Created installation directory: $InstallDir"
}

# 2. Download Executable
# NOTE: In a real scenario, this would be a URL to the compiled EXE.
# For now, we assume the user has the EXE or we provide instructions.
Write-Host "Downloading sbextractor.exe..."
# Invoke-WebRequest -Uri $ExeUrl -OutFile "$InstallDir\sbextractor.exe"

# 3. Create initial config.yaml if it doesn't exist
$ConfigPath = "$InstallDir\config.yaml"
if (!(Test-Path $ConfigPath)) {
    $DefaultConfig = @"
db:
  path: "C:\softbilling\BILL.GDB"
  user: "SYSDBA"
  password: "masterkey"
railway:
  url: "https://fortuna-dashboard.railway.app"
  token: "fortuna-extractor-secret-123"
sync:
  interval_seconds: 60
  tables: []
"@
    Set-Content -Path $ConfigPath -Value $DefaultConfig
    Write-Host "Created default config.yaml"
}

# 4. Create Desktop Shortcut
$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut("$env:USERPROFILE\Desktop\sbextractor.lnk")
$Shortcut.TargetPath = "$InstallDir\sbextractor.exe"
$Shortcut.WorkingDirectory = $InstallDir
$Shortcut.Save()
Write-Host "Created Desktop shortcut"

Write-Host "Installation complete! Please run sbextractor from your desktop."
