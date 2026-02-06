from gui_main import ModernAutoclicker
from PySide6.QtWidgets import QApplication
import sys
import os

# Ensure src is in path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ModernAutoclicker()
    window.show()
    sys.exit(app.exec())
