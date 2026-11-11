import threading
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSpinBox,
    QComboBox, QRadioButton, QButtonGroup, QPushButton, QGroupBox,
    QLineEdit, QFrame
)
from PySide6.QtCore import Qt, Signal, QThread, Slot
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
        self._preset_buttons = []

        self.setup_ui()
        self.status_changed.connect(self.update_ui_state)
        self._update_cps_badge()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(18)

        # --- Page Header ---
        header_row = QHBoxLayout()
        title_col = QVBoxLayout()
        title_col.setSpacing(2)

        title = QLabel("Auto Clicker")
        title.setObjectName("HeaderLabel")
        title_col.addWidget(title)

        subtitle = QLabel("High-precision mouse clicking and automated keyboard trigger engine")
        subtitle.setObjectName("PageSubtitle")
        title_col.addWidget(subtitle)
        header_row.addLayout(title_col)

        header_row.addStretch()

        self.lbl_cps_badge = QLabel("⚡ 1.0 CPS")
        self.lbl_cps_badge.setObjectName("BadgeLabel")
        self.lbl_cps_badge.setAlignment(Qt.AlignCenter)
        header_row.addWidget(self.lbl_cps_badge, alignment=Qt.AlignVCenter)

        layout.addLayout(header_row)

        # --- Interval Group ---
        interval_group = QGroupBox("CLICK INTERVAL")
        interval_outer = QVBoxLayout(interval_group)
        interval_outer.setSpacing(12)

        interval_layout = QHBoxLayout()
        interval_layout.setSpacing(12)

        self.spin_hours, self._sb_hours = self.create_spinbox("Hours", "h", 0, 99, 0)
        self.spin_mins, self._sb_mins = self.create_spinbox("Minutes", "m", 0, 59, 0)
        self.spin_secs, self._sb_secs = self.create_spinbox("Seconds", "s", 0, 59, 1)
        self.spin_ms, self._sb_ms = self.create_spinbox("Milliseconds", "ms", 0, 999, 0)

        interval_layout.addWidget(self.spin_hours)
        interval_layout.addWidget(self.spin_mins)
        interval_layout.addWidget(self.spin_secs)
        interval_layout.addWidget(self.spin_ms)
        interval_outer.addLayout(interval_layout)

        # Quick Presets Row
        presets_row = QHBoxLayout()
        presets_row.setSpacing(8)
        lbl_preset = QLabel("Quick Presets:")
        lbl_preset.setObjectName("FieldLabel")
        presets_row.addWidget(lbl_preset)

        presets = [
            ("10 ms (100 CPS)", 0, 0, 0, 10),
            ("50 ms (20 CPS)", 0, 0, 0, 50),
            ("100 ms (10 CPS)", 0, 0, 0, 100),
            ("250 ms (4 CPS)", 0, 0, 0, 250),
            ("1 sec (1 CPS)", 0, 0, 1, 0),
        ]
        for text, h, m, s, ms in presets:
            btn_p = QPushButton(text)
            btn_p.setObjectName("PresetButton")
            btn_p.setCursor(Qt.PointingHandCursor)
            btn_p.clicked.connect(
                lambda checked=False, h=h, m=m, s=s, ms=ms: self.apply_preset(h, m, s, ms)
            )
            presets_row.addWidget(btn_p)
            self._preset_buttons.append(btn_p)

        presets_row.addStretch()
        interval_outer.addLayout(presets_row)
        layout.addWidget(interval_group)

        # --- Middle Row: Mouse Options & Keyboard Override Side-by-Side ---
        middle_row = QHBoxLayout()
        middle_row.setSpacing(16)

        # 1. Mouse Options Card
        options_group = QGroupBox("MOUSE ACTION")
        options_layout = QVBoxLayout(options_group)
        options_layout.setSpacing(12)

        btn_layout = QVBoxLayout()
        btn_layout.setSpacing(4)
        btn_layout.addWidget(QLabel("Mouse Button", self, objectName="SectionLabel"))
        self.combo_button = QComboBox()
        self.combo_button.addItems(["Left", "Right", "Middle"])
        btn_layout.addWidget(self.combo_button)
        options_layout.addLayout(btn_layout)

        type_layout = QVBoxLayout()
        type_layout.setSpacing(4)
        type_layout.addWidget(QLabel("Click Type", self, objectName="SectionLabel"))
        self.combo_type = QComboBox()
        self.combo_type.addItems(["Single", "Double"])
        type_layout.addWidget(self.combo_type)
        options_layout.addLayout(type_layout)

        options_layout.addStretch()
        middle_row.addWidget(options_group, stretch=1)

        # 2. Keyboard Options Card
        kb_group = QGroupBox("KEYBOARD OVERRIDE (OPTIONAL)")
        kb_layout = QVBoxLayout(kb_group)
        kb_layout.setSpacing(12)

        kb_field = QVBoxLayout()
        kb_field.setSpacing(4)
        kb_field.addWidget(QLabel("Key to Trigger (overrides mouse when set)", objectName="SectionLabel"))
        self.input_kb_key = QLineEdit()
        self.input_kb_key.setPlaceholderText("Leave empty for mouse, or type e.g. 'a', 'space', 'enter'")
        kb_field.addWidget(self.input_kb_key)
        kb_layout.addLayout(kb_field)

        mode_col = QVBoxLayout()
        mode_col.setSpacing(6)
        mode_col.addWidget(QLabel("Key Behavior", objectName="SectionLabel"))
        mode_layout = QHBoxLayout()
        self.radio_press = QRadioButton("Repeat Press")
        self.radio_hold = QRadioButton("Hold Down Continuously")
        self.radio_press.setChecked(True)
        self.kb_mode_group = QButtonGroup(self)
        self.kb_mode_group.addButton(self.radio_press)
        self.kb_mode_group.addButton(self.radio_hold)

        mode_layout.addWidget(self.radio_press)
        mode_layout.addWidget(self.radio_hold)
        mode_layout.addStretch()
        mode_col.addLayout(mode_layout)
        kb_layout.addLayout(mode_col)

        kb_layout.addStretch()
        middle_row.addWidget(kb_group, stretch=1)

        layout.addLayout(middle_row)

        layout.addStretch()

        # --- Action Buttons ---
        action_layout = QHBoxLayout()
        self.btn_start = QPushButton("Start (F6)")
        self.btn_start.setObjectName("PrimaryButton")
        self.btn_start.setCursor(Qt.PointingHandCursor)
        self.btn_start.setMinimumHeight(52)
        self.btn_start.clicked.connect(self.toggle_clicking)

        action_layout.addWidget(self.btn_start)
        layout.addLayout(action_layout)

    def create_spinbox(self, label_text: str, suffix_text: str, min_val: int, max_val: int, default_val: int):
        widget = QFrame()
        widget.setObjectName("SubCard")
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(4)

        label = QLabel(label_text)
        label.setObjectName("FieldLabel")
        label.setAlignment(Qt.AlignCenter)

        spinbox = QSpinBox()
        spinbox.setRange(min_val, max_val)
        spinbox.setValue(default_val)
        spinbox.setSuffix(f" {suffix_text}")
        spinbox.setAlignment(Qt.AlignCenter)
        spinbox.valueChanged.connect(self._update_cps_badge)

        layout.addWidget(label)
        layout.addWidget(spinbox)
        return widget, spinbox

    def apply_preset(self, h: int, m: int, s: int, ms: int):
        if self.is_running:
            return
        self._sb_hours.setValue(h)
        self._sb_mins.setValue(m)
        self._sb_secs.setValue(s)
        self._sb_ms.setValue(ms)
        self._update_cps_badge()

    def _update_cps_badge(self):
        interval = self.get_interval_seconds()
        if interval <= 0:
            self.lbl_cps_badge.setText("⚡ MAX CPS (1000/s)")
        elif interval < 1.0:
            cps = 1.0 / interval
            self.lbl_cps_badge.setText(f"⚡ {cps:.1f} CPS")
        else:
            cps = 1.0 / interval
            self.lbl_cps_badge.setText(f"⏱️ Every {interval:.2f}s ({cps:.2f} CPS)")

    def get_interval_seconds(self) -> float:
        h = self._sb_hours.value()
        m = self._sb_mins.value()
        s = self._sb_secs.value()
        ms = self._sb_ms.value()
        return (h * 3600) + (m * 60) + s + (ms / 1000.0)

    @Slot()
    def toggle_clicking(self):
        if not self.is_running:
            self.start_clicking()
        else:
            self.stop_clicking()

    def start_clicking(self):
        if self.is_running:
            return

        interval = self.get_interval_seconds()
        if interval <= 0:
            interval = 0.001

        kb_key = self.input_kb_key.text().strip().lower()
        is_kb = bool(kb_key)

        config = {
            'interval': interval,
            'action_type': 'key' if is_kb else 'mouse',
            'mouse_btn': self.combo_button.currentText().lower(),
            'click_type': self.combo_type.currentText().lower(),
            'key': kb_key if is_kb else None,
            'key_mode': 'hold' if self.radio_hold.isChecked() else 'press'
        }

        self.stop_event.clear()
        self.clicker = Clicker(self.stop_event)

        # Offload to QThread
        self.clicker_thread = ClickerThread(self.clicker, config)
        self.clicker_thread.finished.connect(self.on_thread_finished)
        self.clicker_thread.start()

        self.status_changed.emit(True)

    def stop_clicking(self):
        if not self.is_running:
            return
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
        self.input_kb_key.setEnabled(not is_running)
        self.radio_press.setEnabled(not is_running)
        self.radio_hold.setEnabled(not is_running)
        for btn in self._preset_buttons:
            btn.setEnabled(not is_running)
