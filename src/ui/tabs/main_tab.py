from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSpinBox, 
    QComboBox, QRadioButton, QButtonGroup, QPushButton, QGroupBox
)
from PySide6.QtCore import Qt, Signal, QThread, Slot
import threading
from src.clicker import Clicker

class ClickerThread(QThread):
    """
    Runs the infinite clicker loop on a separate thread so the GUI 
    doesn't freeze.
    """
    finished = Signal()
    error = Signal(str)

    def __init__(self, clicker_instance, config):
        super().__init__()
        self.clicker = clicker_instance
        self.config = config

    def run(self):
        try:
            self.clicker.run(self.config)
        except Exception as e:
            self.error.emit(str(e))
        finally:
            self.finished.emit()

class MainTab(QWidget):
    # Signals for UI updates from hotkeys
    status_changed = Signal(bool)

    def __init__(self):
        super().__init__()
        
        self.clicker = None
        self.clicker_thread = None
        self.stop_event = threading.Event()
        self.is_running = False

        self.setup_ui()
        self.status_changed.connect(self.update_ui_state)

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        title = QLabel("Main Autoclicker")
        title.setObjectName("HeaderLabel")
        layout.addWidget(title)

        # --- Interval Group ---
        interval_group = QGroupBox("Click Interval")
        interval_layout = QHBoxLayout(interval_group)
        
        self.spin_hours = self.create_spinbox("Hours", 0, 99, 0)
        self.spin_mins = self.create_spinbox("Mins", 0, 59, 0)
        self.spin_secs = self.create_spinbox("Secs", 0, 59, 1)
        self.spin_ms = self.create_spinbox("Ms", 0, 999, 0)
        
        interval_layout.addWidget(self.spin_hours)
        interval_layout.addWidget(self.spin_mins)
        interval_layout.addWidget(self.spin_secs)
        interval_layout.addWidget(self.spin_ms)
        layout.addWidget(interval_group)

        # --- Click Options Group ---
        options_group = QGroupBox("Click Options")
        options_layout = QHBoxLayout(options_group)

        # Mouse Button Selection
        btn_layout = QVBoxLayout()
        btn_layout.addWidget(QLabel("Mouse Button:", self, objectName="SectionLabel"))
        self.combo_button = QComboBox()
        self.combo_button.addItems(["Left", "Right", "Middle"])
        btn_layout.addWidget(self.combo_button)
        options_layout.addLayout(btn_layout)

        # Click Type Selection
        type_layout = QVBoxLayout()
        type_layout.addWidget(QLabel("Click Type:", self, objectName="SectionLabel"))
        self.combo_type = QComboBox()
        self.combo_type.addItems(["Single", "Double"])
        type_layout.addWidget(self.combo_type)
        options_layout.addLayout(type_layout)

        layout.addWidget(options_group)

        # --- Keyboard Options Group ---
        kb_group = QGroupBox("Keyboard Options (Overrides Mouse if set)")
        kb_layout = QVBoxLayout(kb_group)
        
        self.combo_kb_key = QComboBox()
        self.combo_kb_key.addItems(["", "a", "b", "c", "space", "enter"]) # Simplified for now
        kb_layout.addWidget(QLabel("Key to press:", objectName="SectionLabel"))
        kb_layout.addWidget(self.combo_kb_key)

        mode_layout = QHBoxLayout()
        self.radio_press = QRadioButton("Press")
        self.radio_hold = QRadioButton("Hold")
        self.radio_press.setChecked(True)
        self.kb_mode_group = QButtonGroup()
        self.kb_mode_group.addButton(self.radio_press)
        self.kb_mode_group.addButton(self.radio_hold)
        
        self.spin_hold_dur = QSpinBox()
        self.spin_hold_dur.setRange(10, 10000)
        self.spin_hold_dur.setValue(100)
        self.spin_hold_dur.setSuffix(" ms")
        self.spin_hold_dur.setEnabled(False)
        self.radio_hold.toggled.connect(self.spin_hold_dur.setEnabled)

        mode_layout.addWidget(self.radio_press)
        mode_layout.addWidget(self.radio_hold)
        mode_layout.addWidget(self.spin_hold_dur)
        kb_layout.addLayout(mode_layout)

        layout.addWidget(kb_group)

        # --- Action Buttons ---
        action_layout = QHBoxLayout()
        self.btn_start = QPushButton("Start (F6)")
        self.btn_start.setObjectName("PrimaryButton")
        self.btn_start.setMinimumHeight(50)
        self.btn_start.clicked.connect(self.toggle_clicking)
        
        action_layout.addWidget(self.btn_start)
        layout.addLayout(action_layout)

        layout.addStretch()

    def create_spinbox(self, label_text, min_val, max_val, default_val):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        
        label = QLabel(label_text)
        label.setAlignment(Qt.AlignCenter)
        
        spinbox = QSpinBox()
        spinbox.setRange(min_val, max_val)
        spinbox.setValue(default_val)
        spinbox.setAlignment(Qt.AlignCenter)
        
        layout.addWidget(label)
        layout.addWidget(spinbox)
        return widget

    def get_interval_seconds(self) -> float:
        h = self.spin_hours.findChild(QSpinBox).value()
        m = self.spin_mins.findChild(QSpinBox).value()
        s = self.spin_secs.findChild(QSpinBox).value()
        ms = self.spin_ms.findChild(QSpinBox).value()
        return (h * 3600) + (m * 60) + s + (ms / 1000.0)

    @Slot()
    def toggle_clicking(self):
        if not self.is_running:
            self.start_clicking()
        else:
            self.stop_clicking()

    def start_clicking(self):
        if self.is_running: return

        interval = self.get_interval_seconds()
        if interval <= 0: interval = 0.01

        kb_key = self.combo_kb_key.currentText()
        is_kb = bool(kb_key)

        config = {
            'interval': interval,
            'action_type': 'key' if is_kb else 'mouse',
            'mouse_btn': self.combo_button.currentText().lower(),
            'click_type': self.combo_type.currentText().lower(),
            'key': kb_key if is_kb else None,
            'key_mode': 'hold' if self.radio_hold.isChecked() else 'press',
            'hold_dur': self.spin_hold_dur.value()
        }

        self.stop_event.clear()
        self.clicker = Clicker(self.stop_event)
        
        # Offload to QThread
        self.clicker_thread = ClickerThread(self.clicker, config)
        self.clicker_thread.finished.connect(self.on_thread_finished)
        self.clicker_thread.start()

        self.status_changed.emit(True)

    def stop_clicking(self):
        if not self.is_running: return
        self.stop_event.set()
        self.status_changed.emit(False)

    def on_thread_finished(self):
        self.status_changed.emit(False)

    def update_ui_state(self, is_running: bool):
        self.is_running = is_running
        if is_running:
            self.btn_start.setText("Stop (F6)")
            self.btn_start.setObjectName("DangerButton")
        else:
            self.btn_start.setText("Start (F6)")
            self.btn_start.setObjectName("PrimaryButton")
        
        # Force stylesheet re-evaluation to apply the new ObjectName colors
        self.btn_start.style().unpolish(self.btn_start)
        self.btn_start.style().polish(self.btn_start)
        
        # Disable inputs while running
        self.spin_hours.setEnabled(not is_running)
        self.spin_mins.setEnabled(not is_running)
        self.spin_secs.setEnabled(not is_running)
        self.spin_ms.setEnabled(not is_running)
        self.combo_button.setEnabled(not is_running)
        self.combo_type.setEnabled(not is_running)
        self.combo_kb_key.setEnabled(not is_running)
        self.radio_press.setEnabled(not is_running)
        self.radio_hold.setEnabled(not is_running)



