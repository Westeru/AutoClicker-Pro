import time
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QDialog, QComboBox,
    QStackedWidget, QPushButton, QFrame, QLabel, QSpacerItem, QSizePolicy,
    QSystemTrayIcon, QMenu, QDialogButtonBox
)
from PySide6.QtGui import QIcon, QPixmap, QPainter, QColor, QFont, QAction
from PySide6.QtCore import Qt, QMetaObject, QTimer
from src.ui.tabs.main_tab import MainTab
from src.settings_manager import SettingsManager
from pynput import keyboard


AVAILABLE_HOTKEYS = [
    "f1", "f2", "f3", "f4", "f5", "f6", "f7", "f8", "f9", "f10", "f11", "f12",
    "insert", "home", "end", "page_up", "page_down", "pause",
]


def _create_tray_icon() -> QIcon:
    """Create a crisp programmatic app icon for the Windows System Tray."""
    pix = QPixmap(64, 64)
    pix.fill(Qt.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.Antialiasing)
    p.setBrush(QColor("#2563EB"))
    p.setPen(Qt.NoPen)
    p.drawRoundedRect(4, 4, 56, 56, 14, 14)
    p.setPen(QColor("#FFFFFF"))
    p.setFont(QFont("Segoe UI", 28, QFont.Bold))
    p.drawText(pix.rect(), Qt.AlignCenter, "⚡")
    p.end()
    return QIcon(pix)


class HotkeyDialog(QDialog):
    """Modal dialog for rebinding Start/Stop and Record global hotkeys."""

    def __init__(self, current_start: str, current_rec: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Configure Global Hotkeys")
        self.setFixedWidth(340)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        lbl = QLabel("Global Hotkeys")
        lbl.setObjectName("HeaderLabel")
        layout.addWidget(lbl)

        sub = QLabel("Choose keys that don't conflict with your games or apps.")
        sub.setObjectName("PageSubtitle")
        sub.setWordWrap(True)
        layout.addWidget(sub)

        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Start / Stop Active:", objectName="SectionLabel"))
        self.combo_start = QComboBox()
        for k in AVAILABLE_HOTKEYS:
            self.combo_start.addItem(k.upper(), k)
        idx1 = self.combo_start.findData(current_start.lower())
        if idx1 >= 0:
            self.combo_start.setCurrentIndex(idx1)
        row1.addWidget(self.combo_start)
        layout.addLayout(row1)

        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Record Macro Toggle:", objectName="SectionLabel"))
        self.combo_rec = QComboBox()
        for k in AVAILABLE_HOTKEYS:
            self.combo_rec.addItem(k.upper(), k)
        idx2 = self.combo_rec.findData(current_rec.lower())
        if idx2 >= 0:
            self.combo_rec.setCurrentIndex(idx2)
        row2.addWidget(self.combo_rec)
        layout.addLayout(row2)

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_hotkeys(self):
        return self.combo_start.currentData(), self.combo_rec.currentData()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.settings = SettingsManager()
        self.start_hotkey = str(self.settings.get("start_stop_hotkey", "f6")).lower()
        self.record_hotkey = str(self.settings.get("record_hotkey", "f7")).lower()

        # Live Session Telemetry
        self._click_count = 0
        self._session_start_time = None
        self._session_timer = QTimer(self)
        self._session_timer.setInterval(1000)
        self._session_timer.timeout.connect(self._update_session_timer_label)

        self.setWindowTitle("AutoClicker Pro")
        self.setMinimumSize(880, 620)
        self.resize(980, 670)

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

        # 4. System Tray
        self.setup_tray()

        # 5. Global Hotkeys
        self.kb_listener = None
        self.setup_hotkeys()

        # 6. Apply Always-on-Top if persisted
        if self.settings.get("always_on_top", False):
            self.btn_pin.setChecked(True)
            self.toggle_always_on_top(True)

    def setup_sidebar(self):
        """Creates the sleek left navigation sidebar."""
        self.sidebar = QFrame()
        self.sidebar.setObjectName("sidebar")
        self.sidebar.setFixedWidth(232)

        self.sidebar_layout = QVBoxLayout(self.sidebar)
        self.sidebar_layout.setContentsMargins(14, 20, 14, 16)
        self.sidebar_layout.setSpacing(6)

        # Brand Header
        brand_box = QVBoxLayout()
        brand_box.setContentsMargins(6, 0, 6, 8)
        brand_box.setSpacing(2)

        self.title_label = QLabel("⚡ AutoClicker Pro")
        self.title_label.setObjectName("AppLogo")
        brand_box.addWidget(self.title_label)

        self.subtitle_label = QLabel("AUTOMATION SUITE")
        self.subtitle_label.setObjectName("AppSubtitle")
        brand_box.addWidget(self.subtitle_label)
        self.sidebar_layout.addLayout(brand_box)

        # Window Quick Controls (Pin on Top + Minimize to Tray)
        win_ctrl_row = QHBoxLayout()
        win_ctrl_row.setSpacing(6)

        self.btn_pin = QPushButton("📌 Pin")
        self.btn_pin.setObjectName("PresetButton")
        self.btn_pin.setCheckable(True)
        self.btn_pin.setCursor(Qt.PointingHandCursor)
        self.btn_pin.setToolTip("Keep window always on top")
        self.btn_pin.toggled.connect(self.toggle_always_on_top)
        win_ctrl_row.addWidget(self.btn_pin)

        self.btn_tray = QPushButton("🗕 Tray")
        self.btn_tray.setObjectName("PresetButton")
        self.btn_tray.setCursor(Qt.PointingHandCursor)
        self.btn_tray.setToolTip("Minimize to Windows System Tray")
        self.btn_tray.clicked.connect(self.minimize_to_tray)
        win_ctrl_row.addWidget(self.btn_tray)

        self.sidebar_layout.addLayout(win_ctrl_row)

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
        spacer = QSpacerItem(20, 20, QSizePolicy.Minimum, QSizePolicy.Expanding)
        self.sidebar_layout.addItem(spacer)

        # Sidebar Live Telemetry, Status & Hotkey Card
        footer_card = QFrame()
        footer_card.setObjectName("SidebarFooter")
        footer_layout = QVBoxLayout(footer_card)
        footer_layout.setContentsMargins(12, 10, 12, 10)
        footer_layout.setSpacing(6)

        self.lbl_global_status = QLabel("●  System Idle")
        self.lbl_global_status.setObjectName("StatusDotIdle")
        footer_layout.addWidget(self.lbl_global_status)

        self.lbl_session_stats = QLabel("Clicks: 0  •  00:00:00")
        self.lbl_session_stats.setObjectName("HotkeyHint")
        footer_layout.addWidget(self.lbl_session_stats)

        self.lbl_hk1 = QLabel(f"{self.start_hotkey.upper()}  —  Start / Stop Active")
        self.lbl_hk1.setObjectName("HotkeyHint")
        self.lbl_hk2 = QLabel(f"{self.record_hotkey.upper()}  —  Record Macro")
        self.lbl_hk2.setObjectName("HotkeyHint")
        footer_layout.addWidget(self.lbl_hk1)
        footer_layout.addWidget(self.lbl_hk2)

        self.btn_hotkeys = QPushButton("⌨️  Configure Hotkeys")
        self.btn_hotkeys.setObjectName("PresetButton")
        self.btn_hotkeys.setCursor(Qt.PointingHandCursor)
        self.btn_hotkeys.clicked.connect(self.open_hotkey_dialog)
        footer_layout.addWidget(self.btn_hotkeys)

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

    # --- WINDOW PIN & SYSTEM TRAY ---
    def toggle_always_on_top(self, checked: bool):
        self.settings.set("always_on_top", checked)
        was_visible = self.isVisible()
        self.setWindowFlag(Qt.WindowStaysOnTopHint, checked)
        if was_visible:
            self.show()

    def setup_tray(self):
        self.tray_icon = None
        if not QSystemTrayIcon.isSystemTrayAvailable():
            self.btn_tray.setVisible(False)
            return
        self.tray_icon = QSystemTrayIcon(_create_tray_icon(), self)
        self.tray_icon.setToolTip("AutoClicker Pro")

        menu = QMenu(self)
        act_show = QAction("Show AutoClicker Pro", self)
        act_show.triggered.connect(self.restore_from_tray)
        menu.addAction(act_show)

        act_toggle = QAction(f"Start / Stop ({self.start_hotkey.upper()})", self)
        act_toggle.triggered.connect(self.on_f6_pressed)
        menu.addAction(act_toggle)

        menu.addSeparator()
        act_quit = QAction("Exit", self)
        act_quit.triggered.connect(self.close)
        menu.addAction(act_quit)

        self.tray_icon.setContextMenu(menu)
        self.tray_icon.activated.connect(self._on_tray_activated)

    def minimize_to_tray(self):
        if self.tray_icon:
            self.tray_icon.show()
            self.hide()

    def restore_from_tray(self):
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def _on_tray_activated(self, reason):
        if reason in (QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick):
            self.restore_from_tray()

    # --- LIVE CLICK COUNTER & SESSION TIMER ---
    def _on_action_performed(self):
        self._click_count += 1
        self._update_session_timer_label()

    def _update_session_timer_label(self):
        elapsed = 0
        if self._session_start_time is not None:
            elapsed = int(time.time() - self._session_start_time)
        hrs, rem = divmod(elapsed, 3600)
        mins, secs = divmod(rem, 60)
        self.lbl_session_stats.setText(f"Clicks: {self._click_count}  •  {hrs:02d}:{mins:02d}:{secs:02d}")

    def _update_global_status(self, active: bool, mode_name: str = "Running"):
        if active:
            self._click_count = 0
            self._session_start_time = time.time()
            self._session_timer.start()
            self._update_session_timer_label()
            self.lbl_global_status.setText(f"●  {mode_name}")
            self.lbl_global_status.setObjectName("StatusDotActive")
        else:
            self._session_timer.stop()
            self.lbl_global_status.setText("●  System Idle")
            self.lbl_global_status.setObjectName("StatusDotIdle")
        self.lbl_global_status.style().unpolish(self.lbl_global_status)
        self.lbl_global_status.style().polish(self.lbl_global_status)

    # --- TABS ---
    def setup_tabs(self):
        """Initializes and adds tab widgets to the stack lazily."""
        self.tab_main = MainTab(settings_manager=self.settings)
        self.tab_main.set_hotkey_label(self.start_hotkey)
        self.tab_main.status_changed.connect(
            lambda running: self._update_global_status(running, "Clicker Active")
        )
        self.tab_main.action_performed.connect(self._on_action_performed)
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
            self._tab_vision = ImageSearchTab(settings_manager=self.settings)
            self._tab_vision.set_hotkey_label(self.start_hotkey)
            self._tab_vision.status_changed.connect(
                lambda running: self._update_global_status(running, "Vision Active")
            )
            self._tab_vision.action_performed.connect(self._on_action_performed)
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
            self._tab_workflow.set_hotkey_label(self.start_hotkey)
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
            self._tab_record.set_hotkey_labels(self.start_hotkey, self.record_hotkey)
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

    # --- GLOBAL HOTKEYS ---
    def setup_hotkeys(self):
        """Sets up global hotkey listener for configurable start/stop and record keys."""
        if self.kb_listener is not None:
            try:
                if self.kb_listener.is_alive():
                    self.kb_listener.stop()
            except Exception:
                pass
        start_binding = f"<{self.start_hotkey}>"
        rec_binding = f"<{self.record_hotkey}>"
        hotkeys = {start_binding: self.on_f6_pressed}
        if rec_binding != start_binding:
            hotkeys[rec_binding] = self.on_f7_pressed

        self.kb_listener = keyboard.GlobalHotKeys(hotkeys)
        self.kb_listener.daemon = True
        self.kb_listener.start()

    def open_hotkey_dialog(self):
        dlg = HotkeyDialog(self.start_hotkey, self.record_hotkey, self)
        if dlg.exec() == QDialog.Accepted:
            new_start, new_rec = dlg.get_hotkeys()
            self.start_hotkey = new_start
            self.record_hotkey = new_rec
            self.settings.set("start_stop_hotkey", new_start)
            self.settings.set("record_hotkey", new_rec)

            self.lbl_hk1.setText(f"{new_start.upper()}  —  Start / Stop Active")
            self.lbl_hk2.setText(f"{new_rec.upper()}  —  Record Macro")
            self.tab_main.set_hotkey_label(new_start)
            if self._tab_vision:
                self._tab_vision.set_hotkey_label(new_start)
            if self._tab_workflow:
                self._tab_workflow.set_hotkey_label(new_start)
            if self._tab_record:
                self._tab_record.set_hotkey_labels(new_start, new_rec)
            self.setup_hotkeys()

    def on_f6_pressed(self):
        """Called by pynput background thread when Start/Stop hotkey is pressed."""
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
        """Called by pynput background thread when Record Toggle hotkey is pressed."""
        idx = self.content_stack.currentIndex()
        if idx == 3:
            QMetaObject.invokeMethod(self.tab_record, "toggle_recording_hotkey", Qt.QueuedConnection)

    def closeEvent(self, event):
        """Cleanup when the main window is closed."""
        self._session_timer.stop()
        if self.tray_icon:
            self.tray_icon.hide()

        if hasattr(self, 'kb_listener') and self.kb_listener and self.kb_listener.is_alive():
            self.kb_listener.stop()

        if hasattr(self, 'tab_main'):
            self.tab_main.save_last_state()
            if self.tab_main.is_running:
                self.tab_main.stop_clicking()
                if self.tab_main.clicker_thread:
                    self.tab_main.clicker_thread.wait(2000)
        if self._tab_vision:
            self._tab_vision.save_last_state()
            if self._tab_vision.is_running:
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
