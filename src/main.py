import ctypes
import os
import sys

# Add project root to path so 'src' module can be resolved
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Ensure PySide6 is the Qt backend
os.environ["QT_API"] = "pyside6"

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QIcon
from src.ui.main_window import MainWindow


def _resolve_asset(rel_path: str) -> str:
    try:
        base_path = sys._MEIPASS
    except AttributeError:
        base_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    return os.path.join(base_path, rel_path)


def main():
    # Ensure Windows taskbar displays our custom icon instead of the default Python icon
    if sys.platform == "win32":
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Westeru.AutoClickerPro.2")
        except Exception:
            pass

    # Create the Qt Application
    app = QApplication(sys.argv)
    app.setApplicationName("AutoClicker-Pro")

    # Set global application & taskbar icon
    icon_path = _resolve_asset(os.path.join("assets", "app_icon.ico"))
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))

    # Load stylesheet safely
    style_path = _resolve_asset(os.path.join("src", "styles", "dark_theme.qss"))
    if os.path.exists(style_path):
        with open(style_path, "r", encoding="utf-8") as f:
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
