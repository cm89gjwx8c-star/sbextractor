import PyInstaller.__main__
import os

def build():
    # Define the name of the main script
    script_name = "agent.py"
    
    # Define PyInstaller options
    options = [
        '--name=sbextractor',
        '--onefile',
        '--noconsole',  # Don't show console window
        '--add-data=requirements.txt;.',  # Optional: include requirements if needed
        script_name
    ]
    
    # Run PyInstaller
    print(f"Building {script_name} into EXE...")
    PyInstaller.__main__.run(options)
    print("Build complete. Look for sbextractor.exe in the 'dist' folder.")

if __name__ == "__main__":
    if not os.path.exists("agent.py"):
        print("Error: agent.py not found.")
    else:
        build()
