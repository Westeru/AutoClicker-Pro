"""
Build script for AutoClicker-Pro.
Cleans build directory, runs test suite, and compiles using optimized PyInstaller spec.
"""
import os
import shutil
import subprocess
import sys

def get_python_exe():
    # Prefer Python 3.12 or current python if it has PyInstaller
    candidates = [
        [sys.executable],
        ["py", "-3.12"],
        [r"C:\Users\chiha\AppData\Local\Programs\Python\Python312\python.exe"]
    ]
    for cmd in candidates:
        try:
            res = subprocess.run(cmd + ["-m", "PyInstaller", "--version"], capture_output=True, text=True)
            if res.returncode == 0:
                return cmd
        except Exception:
            continue
    return [sys.executable]

def main():
    print("=== AutoClicker-Pro Build Script ===")
    py_cmd = get_python_exe()
    print(f"Using Python interpreter: {' '.join(py_cmd)}")
    
    # 1. Run Tests
    print("\n[1/3] Running tests...")
    test_res = subprocess.run(py_cmd + ["-m", "pytest", "-q"], capture_output=True, text=True)
    if test_res.returncode != 0:
        print("Tests failed! Aborting build.")
        print(test_res.stdout)
        print(test_res.stderr)
        sys.exit(1)
    print("All tests passed successfully!")

    # 2. Clean build artifact folders
    print("\n[2/3] Cleaning previous build cache...")
    for folder in ['build']:
        if os.path.exists(folder):
            try:
                shutil.rmtree(folder)
                print(f"Cleaned {folder}/")
            except Exception as e:
                print(f"Notice: Could not fully delete {folder}: {e}")

    # 3. Run PyInstaller
    print("\n[3/3] Compiling with PyInstaller...")
    cmd = py_cmd + [
        "-m", "PyInstaller",
        "--clean",
        "--noconfirm",
        "AutoClickerPro.spec"
    ]
    res = subprocess.run(cmd)
    if res.returncode != 0:
        print("\nPyInstaller build failed!")
        sys.exit(res.returncode)

    print("\n=== Build Completed Successfully! ===")
    print("Outputs generated:")
    print("  1. Instant Start (Recommended): dist/AutoClickerPro/AutoClickerPro.exe")
    print("  2. Standalone Portable EXE:      dist/AutoClickerPro-Portable.exe")

if __name__ == "__main__":
    main()
