import threading
from typing import Optional
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSpinBox,
    QComboBox, QRadioButton, QButtonGroup, QPushButton, QGroupBox,
    QLineEdit, QFrame, QCheckBox, QInputDialog, QMessageBox
)
from PySide6.QtCore import Qt, Signal, QThread, Slot, QTimer
from src.clicker import Clicker


class ClickerThread(QThread):
    """
    Runs the clicker loop on a separate thread so the GUI doesn't freeze.
    """
    finished = Signal()
    error = Signal(str)
    clicked = Signal()

    def __init__(self, clicker_instance, config):
        super().__init__()
        self.clicker = clicker_instance
        self.config = config
        self.clicker.on_click_callback = self.clicked.emit

    def run(self):
        try:
            self.clicker.run(self.config)
        except Exception as e:
            self.error.emit(str(e))
        finally:
            self.finished.emit()


class MainTab(QWidget):
    # Signals for UI updates from hotkeys & live telemetry
    status_changed = Signal(bool)
    action_performed = Signal()

    def __init__(self, settings_manager=None):
        super().__init__()

        self.settings = settings_manager
        self.clicker = None
        self.clicker_thread = None
        self.stop_event = threading.Event()
        self.is_running = False
        self._preset_buttons = []
        self._hotkey_label = "F6"

        self.setup_ui()
        self.status_changed.connect(self.update_ui_state)
        if self.settings is not None:
            self._load_saved_state()
            self._refresh_profiles()
        self._update_cps_badge()

    def set_hotkey_label(self, key_label: str):
        self._hotkey_label = key_label.upper()
        self.update_ui_state(self.is_running)

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)

        # --- Page Header ---
        header_row = QHBoxLayout()
        title_col = QVBoxLayout()
        title_col.setSpacing(2)

        title = QLabel("Auto Clicker")
        title.setObjectName("HeaderLabel")
        title_col.addWidget(title)

        subtitle = QLabel("High-precision clicking with randomization, repeat limits & saved profiles")
        subtitle.setObjectName("PageSubtitle")
        title_col.addWidget(subtitle)
        header_row.addLayout(title_col)

        header_row.addStretch()

        # Profile Selector Bar
        self.combo_profile = QComboBox()
        self.combo_profile.setMinimumWidth(130)
        self.combo_profile.addItem("Default")
        self.combo_profile.activated.connect(self._on_profile_selected)
        header_row.addWidget(self.combo_profile, alignment=Qt.AlignVCenter)

        self.btn_save_profile = QPushButton("💾")
        self.btn_save_profile.setFixedSize(34, 32)
        self.btn_save_profile.setStyleSheet("padding: 0px;")
        self.btn_save_profile.setToolTip("Save current settings as a named profile")
        self.btn_save_profile.setCursor(Qt.PointingHandCursor)
        self.btn_save_profile.clicked.connect(self.save_current_profile)
        header_row.addWidget(self.btn_save_profile, alignment=Qt.AlignVCenter)

        self.btn_del_profile = QPushButton("🗑️")
        self.btn_del_profile.setFixedSize(34, 32)
        self.btn_del_profile.setStyleSheet("padding: 0px;")
        self.btn_del_profile.setToolTip("Delete selected profile")
        self.btn_del_profile.setCursor(Qt.PointingHandCursor)
        self.btn_del_profile.clicked.connect(self.delete_selected_profile)
        header_row.addWidget(self.btn_del_profile, alignment=Qt.AlignVCenter)

        self.lbl_cps_badge = QLabel("⚡ 1.0 CPS")
        self.lbl_cps_badge.setObjectName("BadgeLabel")
        self.lbl_cps_badge.setAlignment(Qt.AlignCenter)
        header_row.addWidget(self.lbl_cps_badge, alignment=Qt.AlignVCenter)

        layout.addLayout(header_row)

        # --- Interval & Humanization Group ---
        interval_group = QGroupBox("CLICK INTERVAL & RANDOMIZATION")
        interval_outer = QVBoxLayout(interval_group)
        interval_outer.setSpacing(10)

        interval_layout = QHBoxLayout()
        interval_layout.setSpacing(10)

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
        presets_row.setSpacing(6)
        lbl_preset = QLabel("Presets:")
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

        # Humanization & Repeat Row
        adv_row = QHBoxLayout()
        adv_row.setSpacing(12)

        adv_row.addWidget(QLabel("Random Jitter:", objectName="FieldLabel"))
        self.spin_jitter = QSpinBox()
        self.spin_jitter.setRange(0, 5000)
        self.spin_jitter.setValue(0)
        self.spin_jitter.setPrefix("± ")
        self.spin_jitter.setSuffix(" ms")
        self.spin_jitter.setToolTip("Randomly vary each interval by +/- this many milliseconds")
        adv_row.addWidget(self.spin_jitter)

        adv_row.addWidget(QLabel("Pos Offset:", objectName="FieldLabel"))
        self.spin_pos_jitter = QSpinBox()
        self.spin_pos_jitter.setRange(0, 100)
        self.spin_pos_jitter.setValue(0)
        self.spin_pos_jitter.setPrefix("± ")
        self.spin_pos_jitter.setSuffix(" px")
        self.spin_pos_jitter.setToolTip("Randomly shift click coordinates by +/- pixels")
        adv_row.addWidget(self.spin_pos_jitter)

        adv_row.addWidget(QLabel("Repeat Limit:", objectName="FieldLabel"))
        self.spin_repeat = QSpinBox()
        self.spin_repeat.setRange(0, 1000000)
        self.spin_repeat.setValue(0)
        self.spin_repeat.setSpecialValueText("∞ Infinite")
        self.spin_repeat.setToolTip("0 = Loop forever, or enter exact number of clicks before auto-stopping")
        adv_row.addWidget(self.spin_repeat)

        adv_row.addStretch()
        interval_outer.addLayout(adv_row)
        layout.addWidget(interval_group)

        # --- Middle Row: Mouse Options & Keyboard Override Side-by-Side ---
        middle_row = QHBoxLayout()
        middle_row.setSpacing(14)

        # 1. Mouse Options Card
        options_group = QGroupBox("MOUSE ACTION & POSITION")
        options_layout = QVBoxLayout(options_group)
        options_layout.setSpacing(10)

        btn_type_row = QHBoxLayout()
        btn_type_row.setSpacing(10)

        btn_layout = QVBoxLayout()
        btn_layout.setSpacing(4)
        btn_layout.addWidget(QLabel("Mouse Button", self, objectName="SectionLabel"))
        self.combo_button = QComboBox()
        self.combo_button.addItems(["Left", "Right", "Middle"])
        btn_layout.addWidget(self.combo_button)
        btn_type_row.addLayout(btn_layout)

        type_layout = QVBoxLayout()
        type_layout.setSpacing(4)
        type_layout.addWidget(QLabel("Click Type", self, objectName="SectionLabel"))
        self.combo_type = QComboBox()
        self.combo_type.addItems(["Single", "Double"])
        type_layout.addWidget(self.combo_type)
        btn_type_row.addLayout(type_layout)
        options_layout.addLayout(btn_type_row)

        # Fixed Position Controls
        self.chk_fixed_pos = QCheckBox("Click at Fixed Position (X, Y)")
        self.chk_fixed_pos.stateChanged.connect(self._toggle_fixed_pos_inputs)
        options_layout.addWidget(self.chk_fixed_pos)

        pos_row = QHBoxLayout()
        pos_row.setSpacing(6)
        pos_row.addWidget(QLabel("X:", objectName="FieldLabel"))
        self.spin_pos_x = QSpinBox()
        self.spin_pos_x.setRange(-9999, 9999)
        self.spin_pos_x.setValue(0)
        self.spin_pos_x.setEnabled(False)
        pos_row.addWidget(self.spin_pos_x)

        pos_row.addWidget(QLabel("Y:", objectName="FieldLabel"))
        self.spin_pos_y = QSpinBox()
        self.spin_pos_y.setRange(-9999, 9999)
        self.spin_pos_y.setValue(0)
        self.spin_pos_y.setEnabled(False)
        pos_row.addWidget(self.spin_pos_y)

        self.btn_pick_pos = QPushButton("🎯 Pick")
        self.btn_pick_pos.setCursor(Qt.PointingHandCursor)
        self.btn_pick_pos.setEnabled(False)
        self.btn_pick_pos.setToolTip("Capture cursor coordinates after a 3-second delay")
        self.btn_pick_pos.clicked.connect(self.pick_fixed_pos)
        pos_row.addWidget(self.btn_pick_pos)
        options_layout.addLayout(pos_row)

        self.chk_return_cursor = QCheckBox("Return mouse to original position")
        self.chk_return_cursor.setChecked(True)
        self.chk_return_cursor.setEnabled(False)
        options_layout.addWidget(self.chk_return_cursor)

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
        self.btn_start.setMinimumHeight(50)
        self.btn_start.clicked.connect(self.toggle_clicking)

        action_layout.addWidget(self.btn_start)
        layout.addLayout(action_layout)

    def create_spinbox(self, label_text: str, suffix_text: str, min_val: int, max_val: int, default_val: int):
        widget = QFrame()
        widget.setObjectName("SubCard")
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(10, 6, 10, 6)
        layout.setSpacing(3)

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

    def _toggle_fixed_pos_inputs(self):
        enabled = self.chk_fixed_pos.isChecked() and not self.is_running
        self.spin_pos_x.setEnabled(enabled)
        self.spin_pos_y.setEnabled(enabled)
        self.btn_pick_pos.setEnabled(enabled)
        self.chk_return_cursor.setEnabled(enabled)

    def pick_fixed_pos(self):
        QMessageBox.information(self, "Pick Position", "Hover over your target — capturing in 3 seconds!")
        QTimer.singleShot(3000, self._capture_fixed_pos)

    def _capture_fixed_pos(self):
        import pyautogui
        x, y = pyautogui.position()
        self.spin_pos_x.setValue(int(x))
        self.spin_pos_y.setValue(int(y))
        QMessageBox.information(self, "Captured", f"Fixed target set to ({x}, {y})")

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
            self.lbl_cps_badge.setText(f"⏱️ {interval:.2f}s ({cps:.2f} CPS)")

    def get_interval_seconds(self) -> float:
        h = self._sb_hours.value()
        m = self._sb_mins.value()
        s = self._sb_secs.value()
        ms = self._sb_ms.value()
        return (h * 3600) + (m * 60) + s + (ms / 1000.0)

    # --- PROFILES & SETTINGS PERSISTENCE ---
    def export_state(self) -> dict:
        return {
            "hours": self._sb_hours.value(),
            "mins": self._sb_mins.value(),
            "secs": self._sb_secs.value(),
            "ms": self._sb_ms.value(),
            "jitter_ms": self.spin_jitter.value(),
            "pos_jitter_px": self.spin_pos_jitter.value(),
            "repeat_count": self.spin_repeat.value(),
            "mouse_btn": self.combo_button.currentText(),
            "click_type": self.combo_type.currentText(),
            "use_fixed_pos": self.chk_fixed_pos.isChecked(),
            "pos_x": self.spin_pos_x.value(),
            "pos_y": self.spin_pos_y.value(),
            "return_cursor": self.chk_return_cursor.isChecked(),
            "kb_key": self.input_kb_key.text(),
            "kb_hold": self.radio_hold.isChecked(),
        }

    def import_state(self, state: dict) -> None:
        if not isinstance(state, dict) or not state:
            return
        self._sb_hours.setValue(int(state.get("hours", 0)))
        self._sb_mins.setValue(int(state.get("mins", 0)))
        self._sb_secs.setValue(int(state.get("secs", 1)))
        self._sb_ms.setValue(int(state.get("ms", 0)))
        self.spin_jitter.setValue(int(state.get("jitter_ms", 0)))
        self.spin_pos_jitter.setValue(int(state.get("pos_jitter_px", 0)))
        self.spin_repeat.setValue(int(state.get("repeat_count", 0)))
        self.combo_button.setCurrentText(str(state.get("mouse_btn", "Left")))
        self.combo_type.setCurrentText(str(state.get("click_type", "Single")))
        self.chk_fixed_pos.setChecked(bool(state.get("use_fixed_pos", False)))
        self.spin_pos_x.setValue(int(state.get("pos_x", 0)))
        self.spin_pos_y.setValue(int(state.get("pos_y", 0)))
        self.chk_return_cursor.setChecked(bool(state.get("return_cursor", True)))
        self.input_kb_key.setText(str(state.get("kb_key", "")))
        if state.get("kb_hold", False):
            self.radio_hold.setChecked(True)
        else:
            self.radio_press.setChecked(True)
        self._toggle_fixed_pos_inputs()
        self._update_cps_badge()

    def _load_saved_state(self):
        last = self.settings.get("last_main_state")
        if last:
            self.import_state(last)

    def save_last_state(self):
        if self.settings is not None:
            self.settings.set("last_main_state", self.export_state())

    def _refresh_profiles(self):
        if self.settings is None:
            return
        curr = self.combo_profile.currentText()
        self.combo_profile.blockSignals(True)
        self.combo_profile.clear()
        self.combo_profile.addItem("Default")
        for name in self.settings.list_profiles():
            self.combo_profile.addItem(name)
        idx = self.combo_profile.findText(curr)
        if idx >= 0:
            self.combo_profile.setCurrentIndex(idx)
        self.combo_profile.blockSignals(False)

    def _on_profile_selected(self):
        if self.settings is None:
            return
        name = self.combo_profile.currentText()
        if name == "Default":
            self.import_state({})
            self.apply_preset(0, 0, 1, 0)
            return
        prof = self.settings.get_profile(name)
        if prof:
            self.import_state(prof)

    def save_current_profile(self):
        if self.settings is None:
            return
        name, ok = QInputDialog.getText(self, "Save Profile", "Profile name (e.g. 'Gaming', 'Daily Claim'):")
        if ok and name.strip():
            self.settings.save_profile(name.strip(), self.export_state())
            self._refresh_profiles()
            self.combo_profile.setCurrentText(name.strip())

    def delete_selected_profile(self):
        if self.settings is None:
            return
        name = self.combo_profile.currentText()
        if name == "Default":
            return
        self.settings.delete_profile(name)
        self._refresh_profiles()

    # --- EXECUTION ---
    @Slot()
    def toggle_clicking(self):
        if not self.is_running:
            self.start_clicking()
        else:
            self.stop_clicking()

    def start_clicking(self):
        if self.is_running:
            return

        self.save_last_state()
        interval = self.get_interval_seconds()
        if interval <= 0:
            interval = 0.001

        kb_key = self.input_kb_key.text().strip().lower()
        is_kb = bool(kb_key)

        fixed_pos: Optional[tuple] = None
        if self.chk_fixed_pos.isChecked():
            fixed_pos = (self.spin_pos_x.value(), self.spin_pos_y.value())

        config = {
            'interval': interval,
            'action_type': 'key' if is_kb else 'mouse',
            'mouse_btn': self.combo_button.currentText().lower(),
            'click_type': self.combo_type.currentText().lower(),
            'key': kb_key if is_kb else None,
            'key_mode': 'hold' if self.radio_hold.isChecked() else 'press',
            'repeat_count': self.spin_repeat.value(),
            'jitter_ms': self.spin_jitter.value(),
            'pos_jitter_px': self.spin_pos_jitter.value(),
            'fixed_pos': fixed_pos,
            'return_cursor': self.chk_return_cursor.isChecked(),
        }

        self.stop_event.clear()
        self.clicker = Clicker(self.stop_event)

        # Offload to QThread
        self.clicker_thread = ClickerThread(self.clicker, config)
        self.clicker_thread.clicked.connect(self.action_performed.emit)
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
        hk = self._hotkey_label
        if is_running:
            self.btn_start.setText(f"Stop ({hk})")
            self.btn_start.setObjectName("DangerButton")
        else:
            self.btn_start.setText(f"Start ({hk})")
            self.btn_start.setObjectName("PrimaryButton")

        self.btn_start.style().unpolish(self.btn_start)
        self.btn_start.style().polish(self.btn_start)

        # Disable inputs while running
        self.spin_hours.setEnabled(not is_running)
        self.spin_mins.setEnabled(not is_running)
        self.spin_secs.setEnabled(not is_running)
        self.spin_ms.setEnabled(not is_running)
        self.spin_jitter.setEnabled(not is_running)
        self.spin_pos_jitter.setEnabled(not is_running)
        self.spin_repeat.setEnabled(not is_running)
        self.combo_button.setEnabled(not is_running)
        self.combo_type.setEnabled(not is_running)
        self.chk_fixed_pos.setEnabled(not is_running)
        self._toggle_fixed_pos_inputs()
        self.input_kb_key.setEnabled(not is_running)
        self.radio_press.setEnabled(not is_running)
        self.radio_hold.setEnabled(not is_running)
        self.combo_profile.setEnabled(not is_running)
        self.btn_save_profile.setEnabled(not is_running)
        self.btn_del_profile.setEnabled(not is_running)
        for btn in self._preset_buttons:
            btn.setEnabled(not is_running)
