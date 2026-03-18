import os
import subprocess
import shutil
import zipfile
import sys

def build():
    print("--- Starting Build Process ---")
    
    # 1. Cleanup old builds
    for folder in ['build', 'dist']:
        if os.path.exists(folder):
            shutil.rmtree(folder)
            
    # 2. Run PyInstaller
    # --onefile: single exe
    # --windowed: no console window
    # --name: output name
    # --noconfirm: overwrite existing
    # --clean: clean cache
    print("Running PyInstaller...")
    try:
        subprocess.run([
            'pyinstaller',
            '--noconfirm',
            '--onefile',
            '--windowed',
            '--name', 'sbextractor',
            'agent.py'
        ], check=True)
    except subprocess.CalledProcessError as e:
        print(f"Error during PyInstaller execution: {e}")
        sys.exit(1)
        
    # 3. Prepare Release Package
    print("Preparing release package...")
    release_dir = 'release_pkg'
    if os.path.exists(release_dir):
        shutil.rmtree(release_dir)
    os.makedirs(release_dir)
    
    # Copy EXE
    shutil.copy(os.path.join('dist', 'sbextractor.exe'), release_dir)
    
    # Copy supporting files
    files_to_copy = ['config.yaml', 'install_autostart.bat', 'fbclient.dll']
    for f in files_to_copy:
        if os.path.exists(f):
            shutil.copy(f, release_dir)
        else:
            print(f"Warning: {f} not found, skipping.")
            
    # 4. Create ZIP
    zip_name = 'release.zip'
    print(f"Creating {zip_name}...")
    with zipfile.ZipFile(zip_name, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(release_dir):
            for file in files:
                zipf.write(
                    os.path.join(root, file),
                    os.path.relpath(os.path.join(root, file), release_dir)
                )
                
    print(f"--- Build Complete! {zip_name} is ready ---")

if __name__ == "__main__":
    build()
