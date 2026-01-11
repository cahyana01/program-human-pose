import subprocess
import sys
import importlib.util

def check_and_install():
    # List of required packages
    # Format: (import_name, pip_install_name)
    required_packages = [
        ("flask", "flask"),
        ("ultralytics", "ultralytics"),
        ("cv2", "opencv-python"), # Note: user has opencv-python-headless in requirements, but for GUI opencv-python is often better unless on server
        ("numpy", "numpy"),
        ("PIL", "pillow")
    ]

    print("=== Martial Arts Library Checker ===")
    
    missing_packages = []
    
    for import_name, install_name in required_packages:
        spec = importlib.util.find_spec(import_name)
        if spec is None:
            print(f"[MISSING] {import_name} is not installed.")
            missing_packages.append(install_name)
        else:
            print(f"[FOUND] {import_name} is already installed.")

    if not missing_packages:
        print("\nAll libraries are installed and ready to use!")
        return

    print(f"\nFound {len(missing_packages)} missing packages. Starting installation...")
    
    for package in missing_packages:
        try:
            print(f"\nInstalling {package}...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", package])
            print(f"Successfully installed {package}")
        except subprocess.CalledProcessError as e:
            print(f"Failed to install {package}. Error: {e}")
            sys.exit(1)

    print("\nAll missing libraries have been installed successfully!")

if __name__ == "__main__":
    check_and_install()
    print("\nYou can now run 'python app.py' to start the application.")
