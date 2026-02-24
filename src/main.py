import os
import sys

# Add project root to path so 'src' module can be resolved
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Ensure PySide6 is the Qt backend
os.environ["QT_API"] = "pyside6"

from PySide6.QtWidgets import QApplication
from src.ui.main_window import MainWindow

def main():
    # Create the Qt Application
    app = QApplication(sys.argv)
    
    # Optional: Set global app properties
    app.setApplicationName("AutoClicker-Pro")
    
    # Load stylesheet safely
    try:
        base_path = sys._MEIPASS
        # in PyInstaller, we bundled it as src/styles
        style_path = os.path.join(base_path, "src", "styles", "dark_theme.qss")
    except AttributeError:
        base_path = os.path.dirname(os.path.abspath(__file__))
        style_path = os.path.join(base_path, "styles", "dark_theme.qss")
        
    if os.path.exists(style_path):
        with open(style_path, "r") as f:
            app.setStyleSheet(f.read())
    else:
        print(f"Warning: Stylesheet not found at {style_path}")

    # Initialize and show main window
    window = MainWindow()
    window.show()

    # Run the event loop
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
