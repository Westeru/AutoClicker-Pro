from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QStackedWidget, QPushButton, QFrame, QLabel, QSpacerItem, QSizePolicy
)
from PySide6.QtCore import Qt, QMetaObject
from src.ui.tabs.main_tab import MainTab
from pynput import keyboard


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("AutoClicker Pro")
        self.setMinimumSize(860, 600)
        self.resize(940, 650)

        # Central Widget & Main Layout
        self.central_widget = QWidget()
        self.central_widget.setObjectName("centralwidget")
        self.setCentralWidget(self.central_widget)
        self.main_layout = QHBoxLayout(self.central_widget)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        # 1. Sidebar Setup
        self.setup_sidebar()

        # 2. Main Content Area (Stacked Widget)
        self.content_stack = QStackedWidget()
        self.main_layout.addWidget(self.content_stack, stretch=1)

        # 3. Initialize Tabs (Lazy loaded for secondary tabs)
        self.setup_tabs()

        # 4. Global Hotkeys
        self.setup_hotkeys()

    def setup_sidebar(self):
        """Creates the sleek left navigation sidebar."""
        self.sidebar = QFrame()
        self.sidebar.setObjectName("sidebar")
        self.sidebar.setFixedWidth(232)

        self.sidebar_layout = QVBoxLayout(self.sidebar)
        self.sidebar_layout.setContentsMargins(14, 22, 14, 18)
        self.sidebar_layout.setSpacing(6)

        # Brand Header
        brand_box = QVBoxLayout()
        brand_box.setContentsMargins(8, 0, 8, 12)
        brand_box.setSpacing(2)

        self.title_label = QLabel("⚡ AutoClicker Pro")
        self.title_label.setObjectName("AppLogo")
        brand_box.addWidget(self.title_label)

        self.subtitle_label = QLabel("AUTOMATION SUITE")
        self.subtitle_label.setObjectName("AppSubtitle")
        brand_box.addWidget(self.subtitle_label)

        self.sidebar_layout.addLayout(brand_box)

        # Section Category Label
        nav_cat = QLabel("MODULES")
        nav_cat.setObjectName("NavCategory")
        self.sidebar_layout.addWidget(nav_cat)

        # Navigation Buttons
        self.nav_buttons = {}

        self.btn_main = self.create_nav_button("🖱️   Auto Clicker", 0)
        self.btn_vision = self.create_nav_button("🎯   Image Search", 1)
        self.btn_workflow = self.create_nav_button("⚡   Workflow Builder", 2)
        self.btn_record = self.create_nav_button("⏺️   Macro Recorder", 3)

        # Spacer to push footer to bottom
        spacer = QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding)
        self.sidebar_layout.addItem(spacer)

        # Sidebar Status & Hotkey Card
        footer_card = QFrame()
        footer_card.setObjectName("SidebarFooter")
        footer_layout = QVBoxLayout(footer_card)
        footer_layout.setContentsMargins(12, 10, 12, 10)
        footer_layout.setSpacing(6)

        self.lbl_global_status = QLabel("●  System Idle")
        self.lbl_global_status.setObjectName("StatusDotIdle")
        footer_layout.addWidget(self.lbl_global_status)

        lbl_hk1 = QLabel("F6  —  Start / Stop Active")
        lbl_hk1.setObjectName("HotkeyHint")
        lbl_hk2 = QLabel("F7  —  Record Macro")
        lbl_hk2.setObjectName("HotkeyHint")
        footer_layout.addWidget(lbl_hk1)
        footer_layout.addWidget(lbl_hk2)

        self.sidebar_layout.addWidget(footer_card)
        self.main_layout.addWidget(self.sidebar)

        # Set default active button
        self.btn_main.setChecked(True)

    def create_nav_button(self, text: str, index: int) -> QPushButton:
        """Helper to create sidebar navigation buttons."""
        btn = QPushButton(text)
        btn.setObjectName("NavButton")
        btn.setCursor(Qt.PointingHandCursor)
        btn.setCheckable(True)
        btn.setAutoExclusive(True)
        btn.clicked.connect(lambda: self.switch_tab(index))
        self.sidebar_layout.addWidget(btn)
        self.nav_buttons[index] = btn
        return btn

    def _update_global_status(self, active: bool, mode_name: str = "Running"):
        if active:
            self.lbl_global_status.setText(f"●  {mode_name}")
            self.lbl_global_status.setObjectName("StatusDotActive")
        else:
            self.lbl_global_status.setText("●  System Idle")
            self.lbl_global_status.setObjectName("StatusDotIdle")
        self.lbl_global_status.style().unpolish(self.lbl_global_status)
        self.lbl_global_status.style().polish(self.lbl_global_status)

    def setup_tabs(self):
        """Initializes and adds tab widgets to the stack lazily."""
        self.tab_main = MainTab()
        self.tab_main.status_changed.connect(
            lambda running: self._update_global_status(running, "Clicker Active")
        )
        self._tab_vision = None
        self._tab_workflow = None
        self._tab_record = None

        self.placeholder_vision = QWidget()
        self.placeholder_workflow = QWidget()
        self.placeholder_record = QWidget()

        self.content_stack.addWidget(self.tab_main)             # Index 0
        self.content_stack.addWidget(self.placeholder_vision)   # Index 1
        self.content_stack.addWidget(self.placeholder_workflow) # Index 2
        self.content_stack.addWidget(self.placeholder_record)   # Index 3

    @property
    def tab_vision(self):
        if self._tab_vision is None:
            from src.ui.tabs.image_search_tab import ImageSearchTab
            self._tab_vision = ImageSearchTab()
            self._tab_vision.status_changed.connect(
                lambda running: self._update_global_status(running, "Vision Active")
            )
            cur_idx = self.content_stack.currentIndex()
            self.content_stack.removeWidget(self.placeholder_vision)
            self.content_stack.insertWidget(1, self._tab_vision)
            self.content_stack.setCurrentIndex(cur_idx)
        return self._tab_vision

    @property
    def tab_workflow(self):
        if self._tab_workflow is None:
            from src.ui.tabs.workflow_tab import WorkflowTab
            self._tab_workflow = WorkflowTab()
            self._tab_workflow.status_changed.connect(
                lambda running: self._update_global_status(running, "Workflow Active")
            )
            cur_idx = self.content_stack.currentIndex()
            self.content_stack.removeWidget(self.placeholder_workflow)
            self.content_stack.insertWidget(2, self._tab_workflow)
            self.content_stack.setCurrentIndex(cur_idx)
        return self._tab_workflow

    @property
    def tab_record(self):
        if self._tab_record is None:
            from src.ui.tabs.record_tab import RecordTab
            self._tab_record = RecordTab()
            self._tab_record.status_changed.connect(
                lambda running: self._update_global_status(running, "Playing Macro")
            )
            self._tab_record.recording_changed.connect(
                lambda rec: self._update_global_status(rec, "Recording...")
            )
            cur_idx = self.content_stack.currentIndex()
            self.content_stack.removeWidget(self.placeholder_record)
            self.content_stack.insertWidget(3, self._tab_record)
            self.content_stack.setCurrentIndex(cur_idx)
        return self._tab_record

    def switch_tab(self, index: int):
        """Switches the visible widget in the QStackedWidget."""
        if index == 1:
            _ = self.tab_vision
        elif index == 2:
            _ = self.tab_workflow
        elif index == 3:
            _ = self.tab_record
        if index in self.nav_buttons:
            self.nav_buttons[index].setChecked(True)
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
        idx = self.content_stack.currentIndex()
        if idx == 0:
            QMetaObject.invokeMethod(self.tab_main, "toggle_clicking", Qt.QueuedConnection)
        elif idx == 1:
            QMetaObject.invokeMethod(self.tab_vision, "toggle_clicking", Qt.QueuedConnection)
        elif idx == 2:
            QMetaObject.invokeMethod(self.tab_workflow, "toggle_clicking", Qt.QueuedConnection)
        elif idx == 3:
            QMetaObject.invokeMethod(self.tab_record, "toggle_clicking", Qt.QueuedConnection)

    def on_f7_pressed(self):
        """Called by pynput background thread when F7 is pressed (Record Toggle)."""
        idx = self.content_stack.currentIndex()
        if idx == 3:
            QMetaObject.invokeMethod(self.tab_record, "toggle_recording_hotkey", Qt.QueuedConnection)

    def closeEvent(self, event):
        """Cleanup when the main window is closed."""
        if hasattr(self, 'kb_listener') and self.kb_listener.is_alive():
            self.kb_listener.stop()

        # Stop autoclicker if it's currently running
        if hasattr(self, 'tab_main') and self.tab_main.is_running:
            self.tab_main.stop_clicking()
            if self.tab_main.clicker_thread:
                self.tab_main.clicker_thread.wait(2000)
        if self._tab_vision and self._tab_vision.is_running:
            self._tab_vision.stop_search()
            if self._tab_vision.vision_thread:
                self._tab_vision.vision_thread.wait(2000)
        if self._tab_workflow and self._tab_workflow.is_running:
            self._tab_workflow.stop_workflow()
            if self._tab_workflow.worker_thread:
                self._tab_workflow.worker_thread.wait(2000)
        if self._tab_record:
            if self._tab_record.is_playing:
                self._tab_record.stop_playback()
                if self._tab_record.player_thread:
                    self._tab_record.player_thread.wait(2000)
            if self._tab_record.recorder.recording:
                self._tab_record.recorder.stop()

        super().closeEvent(event)
