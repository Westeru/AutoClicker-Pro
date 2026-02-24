from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QStackedWidget, QPushButton, QFrame, QLabel, QSpacerItem, QSizePolicy
)
from PySide6.QtCore import Qt
from src.ui.tabs.main_tab import MainTab
from src.ui.tabs.record_tab import RecordTab
from src.ui.tabs.image_search_tab import ImageSearchTab
from src.ui.tabs.workflow_tab import WorkflowTab
from pynput import keyboard

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        
        self.setWindowTitle("AutoClicker-Pro")
        self.setMinimumSize(800, 600)
        
        # Central Widget & Main Layout
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QHBoxLayout(self.central_widget)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)
        
        # 1. Sidebar Setup
        self.setup_sidebar()
        
        # 2. Main Content Area (Stacked Widget)
        self.content_stack = QStackedWidget()
        self.main_layout.addWidget(self.content_stack, stretch=1)
        
        # 3. Initialize Tabs
        self.setup_tabs()

        # 4. Global Hotkeys
        self.setup_hotkeys()
        
    def setup_sidebar(self):
        """Creates the left navigation sidebar."""
        self.sidebar = QFrame()
        self.sidebar.setObjectName("sidebar")
        self.sidebar.setFixedWidth(200)
        
        self.sidebar_layout = QVBoxLayout(self.sidebar)
        self.sidebar_layout.setContentsMargins(10, 20, 10, 20)
        self.sidebar_layout.setSpacing(5)
        
        # Title/Logo Area
        self.title_label = QLabel("AutoClicker Pro")
        self.title_label.setObjectName("HeaderLabel")
        self.title_label.setAlignment(Qt.AlignCenter)
        self.title_label.setStyleSheet("font-size: 18px; font-weight: bold; margin-bottom: 20px;")
        self.sidebar_layout.addWidget(self.title_label)
        
        # Navigation Buttons
        self.nav_buttons = {}
        
        self.btn_main = self.create_nav_button("🖱️ Main", 0)
        self.btn_vision = self.create_nav_button("🖼️ Image Search", 1)
        self.btn_workflow = self.create_nav_button("⚙️ Workflow", 2)
        self.btn_record = self.create_nav_button("📼 Record", 3)
        
        # Spacer to push buttons to top
        spacer = QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding)
        self.sidebar_layout.addItem(spacer)
        
        self.main_layout.addWidget(self.sidebar)
        
        # Set default active button
        self.btn_main.setChecked(True)

    def create_nav_button(self, text: str, index: int) -> QPushButton:
        """Helper to create sidebar navigation buttons."""
        btn = QPushButton(text)
        btn.setObjectName("NavButton")
        btn.setCheckable(True)
        btn.setAutoExclusive(True) # Ensures only one tab is active at a time
        btn.clicked.connect(lambda: self.switch_tab(index))
        self.sidebar_layout.addWidget(btn)
        self.nav_buttons[index] = btn
        return btn

    def setup_tabs(self):
        """Initializes and adds the actual tab widgets to the stack."""
        
        # Real Tabs
        self.tab_main = MainTab()
        self.tab_vision = ImageSearchTab()
        self.tab_workflow = WorkflowTab()
        self.tab_record = RecordTab()
        
        self.content_stack.addWidget(self.tab_main)     # Index 0
        self.content_stack.addWidget(self.tab_vision)   # Index 1
        self.content_stack.addWidget(self.tab_workflow) # Index 2
        self.content_stack.addWidget(self.tab_record)   # Index 3

    def switch_tab(self, index: int):
        """Switches the visible widget in the QStackedWidget."""
        self.content_stack.setCurrentIndex(index)

    def setup_hotkeys(self):
        """Sets up global hotkey listener for F6 and F7."""
        self.kb_listener = keyboard.GlobalHotKeys({
            '<f6>': self.on_f6_pressed,
            '<f7>': self.on_f7_pressed
        })
        self.kb_listener.daemon = True
        self.kb_listener.start()

    def on_f6_pressed(self):
        """Called by pynput background thread when F6 is pressed."""
        import PySide6.QtCore as QtCore
        idx = self.content_stack.currentIndex()
        if idx == 0:
            QtCore.QMetaObject.invokeMethod(self.tab_main, "toggle_clicking", QtCore.Qt.QueuedConnection)
        elif idx == 1:
            QtCore.QMetaObject.invokeMethod(self.tab_vision, "toggle_clicking", QtCore.Qt.QueuedConnection)
        elif idx == 2:
            QtCore.QMetaObject.invokeMethod(self.tab_workflow, "toggle_clicking", QtCore.Qt.QueuedConnection)
        elif idx == 3:
            QtCore.QMetaObject.invokeMethod(self.tab_record, "toggle_clicking", QtCore.Qt.QueuedConnection)

    def on_f7_pressed(self):
        """Called by pynput background thread when F7 is pressed (Record Toggle)."""
        import PySide6.QtCore as QtCore
        idx = self.content_stack.currentIndex()
        if idx == 3:
            QtCore.QMetaObject.invokeMethod(self.tab_record, "toggle_recording_hotkey", QtCore.Qt.QueuedConnection)

    def closeEvent(self, event):
        """Cleanup when the main window is closed."""
        if hasattr(self, 'kb_listener') and self.kb_listener.is_alive():
            self.kb_listener.stop()
        
        # Stop autoclicker if it's currently running
        if self.tab_main.is_running:
            self.tab_main.stop_clicking()
        if self.tab_vision.is_running:
            self.tab_vision.stop_search()
        if self.tab_workflow.is_running:
            self.tab_workflow.stop_workflow()
        if self.tab_record.is_playing:
            self.tab_record.stop_playback()
        if self.tab_record.recorder.recording:
            self.tab_record.recorder.stop()
            
        super().closeEvent(event)
