import json
import threading
import time
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QCheckBox,
    QSlider, QListWidget, QPushButton, QFileDialog, QGroupBox, QFrame, QSpinBox
)
from PySide6.QtCore import Qt, Signal, QThread, Slot
from src.recorder import Recorder
from pynput.mouse import Button, Controller as MouseController
from pynput.keyboard import Key, Controller as KeyboardController


class MacroPlayerThread(QThread):
    finished = Signal()
    error = Signal(str)

    def __init__(
        self,
        events,
        speed_multiplier: float,
        stop_event,
        smart_move: bool = False,
        repeat_count: int = 1,
    ):
        super().__init__()
        self.events = events
        self.speed = max(0.1, float(speed_multiplier))
        self.stop_event = stop_event
        self.smart_move = smart_move
        self.repeat_count = max(0, int(repeat_count))
        self.mouse = MouseController()
        self.keyboard = KeyboardController()

    @staticmethod
    def _resolve_key(key_str: str):
        """Convert a stored key string back to a pynput Key enum or character."""
        if key_str.startswith('Key.'):
            try:
                return getattr(Key, key_str.replace('Key.', ''))
            except AttributeError:
                return key_str
        return key_str

    def run(self):
        try:
            if not self.events:
                return

            base_event_time = self.events[0]['time']
            is_stopped = self.stop_event.is_set
            iteration = 0

            while not is_stopped():
                if self.repeat_count > 0 and iteration >= self.repeat_count:
                    break

                start_perf = time.perf_counter()
                for ev in self.events:
                    if is_stopped():
                        break

                    ev_type = ev['type']
                    if self.smart_move and ev_type == 'move':
                        continue

                    # Drift-free wall-clock scheduling
                    target_elapsed = (ev['time'] - base_event_time) / self.speed
                    while not is_stopped():
                        remaining = target_elapsed - (time.perf_counter() - start_perf)
                        if remaining <= 0.001:
                            break
                        time.sleep(min(0.02, remaining))

                    if is_stopped():
                        break

                    if ev_type == 'move':
                        self.mouse.position = (ev['x'], ev['y'])
                    elif ev_type == 'click':
                        self.mouse.position = (ev['x'], ev['y'])
                        btn = getattr(Button, ev['button'], Button.left)
                        if ev.get('pressed', False):
                            self.mouse.press(btn)
                        else:
                            self.mouse.release(btn)
                    elif ev_type == 'scroll':
                        self.mouse.position = (ev['x'], ev['y'])
                        self.mouse.scroll(ev['dx'], ev['dy'])
                    elif ev_type == 'key_press':
                        self.keyboard.press(self._resolve_key(ev['key']))
                    elif ev_type == 'key_release':
                        self.keyboard.release(self._resolve_key(ev['key']))

                iteration += 1
        except Exception as e:
            self.error.emit(str(e))
        finally:
            self.finished.emit()


class RecordTab(QWidget):
    status_changed = Signal(bool)     # playing back
    recording_changed = Signal(bool)  # active recording

    def __init__(self):
        super().__init__()

        self.recorder = Recorder()
        self.player_thread = None
        self.stop_event = threading.Event()

        self.is_playing = False
        self._start_hotkey_label = "F6"
        self._rec_hotkey_label = "F7"

        self.setup_ui()
        self.status_changed.connect(self.update_playback_ui)
        self.recording_changed.connect(self.update_recording_ui)

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(16)

        # --- Page Header ---
        header_row = QHBoxLayout()
        header_col = QVBoxLayout()
        header_col.setSpacing(2)

        title = QLabel("Macro Recorder")
        title.setObjectName("HeaderLabel")
        header_col.addWidget(title)

        subtitle = QLabel("Capture and replay exact mouse & keyboard sequences with drift-free timing")
        subtitle.setObjectName("PageSubtitle")
        header_col.addWidget(subtitle)
        header_row.addLayout(header_col)
        header_row.addStretch()

        self.lbl_rec_status = QLabel("●  Ready to Record")
        self.lbl_rec_status.setObjectName("StatusBanner")
        self.lbl_rec_status.setAlignment(Qt.AlignCenter)
        header_row.addWidget(self.lbl_rec_status, alignment=Qt.AlignVCenter)
        layout.addLayout(header_row)

        # --- Controls Card ---
        ctrl_card = QFrame()
        ctrl_card.setObjectName("Card")
        ctrl_card_layout = QVBoxLayout(ctrl_card)
        ctrl_card_layout.setContentsMargins(16, 14, 16, 14)
        ctrl_card_layout.setSpacing(12)

        ctrl_layout = QHBoxLayout()
        ctrl_layout.setSpacing(10)

        self.btn_rec = QPushButton("⏺️  RECORD (F7)")
        self.btn_rec.setObjectName("DangerButton")
        self.btn_rec.setCursor(Qt.PointingHandCursor)
        self.btn_rec.setMinimumHeight(40)
        self.btn_rec.clicked.connect(self.toggle_recording)
        ctrl_layout.addWidget(self.btn_rec, stretch=2)

        btn_clear = QPushButton("🗑️  Clear")
        btn_clear.setCursor(Qt.PointingHandCursor)
        btn_clear.setMinimumHeight(40)
        btn_clear.clicked.connect(self.clear_macro)
        ctrl_layout.addWidget(btn_clear, stretch=1)

        btn_save = QPushButton("💾  Save Macro")
        btn_save.setCursor(Qt.PointingHandCursor)
        btn_save.setMinimumHeight(40)
        btn_save.clicked.connect(self.save_macro)
        ctrl_layout.addWidget(btn_save, stretch=1)

        btn_load = QPushButton("📂  Load Macro")
        btn_load.setCursor(Qt.PointingHandCursor)
        btn_load.setMinimumHeight(40)
        btn_load.clicked.connect(self.load_macro)
        ctrl_layout.addWidget(btn_load, stretch=1)

        ctrl_card_layout.addLayout(ctrl_layout)

        # Options Row inside Card
        opts_layout = QHBoxLayout()
        self.chk_straight_line = QCheckBox("Global Smart Move (Teleport directly to click targets)")
        self.chk_straight_line.setToolTip("Skip intermediate mouse movements and jump directly to click/scroll coordinates")
        opts_layout.addWidget(self.chk_straight_line)

        opts_layout.addStretch()

        opts_layout.addWidget(QLabel("Playback Speed:", objectName="SectionLabel"))
        self.slider_speed = QSlider(Qt.Horizontal)
        self.slider_speed.setRange(5, 50)  # 0.5x to 5.0x
        self.slider_speed.setValue(10)     # 1.0x
        self.slider_speed.setFixedWidth(160)

        self.lbl_speed_val = QLabel("1.0x")
        self.lbl_speed_val.setObjectName("BadgeLabel")
        self.slider_speed.valueChanged.connect(lambda v: self.lbl_speed_val.setText(f"{v/10.0:.1f}x"))
        opts_layout.addWidget(self.slider_speed)
        opts_layout.addWidget(self.lbl_speed_val)

        ctrl_card_layout.addLayout(opts_layout)
        layout.addWidget(ctrl_card)

        # --- Event List Display ---
        log_group = QGroupBox("RECORDED ACTION TIMELINE")
        log_layout = QVBoxLayout(log_group)
        self.list_events = QListWidget()
        log_layout.addWidget(self.list_events)
        layout.addWidget(log_group, stretch=1)

        # --- Play + Repeat Row ---
        play_row = QHBoxLayout()
        play_row.setSpacing(10)

        self.spin_macro_repeat = QSpinBox()
        self.spin_macro_repeat.setRange(0, 10000)
        self.spin_macro_repeat.setValue(1)
        self.spin_macro_repeat.setSpecialValueText("∞ Loop")
        self.spin_macro_repeat.setPrefix("×")
        self.spin_macro_repeat.setMinimumHeight(52)
        self.spin_macro_repeat.setFixedWidth(100)
        self.spin_macro_repeat.setToolTip("Number of times to replay macro (0 = Loop Forever)")
        play_row.addWidget(self.spin_macro_repeat)

        self.btn_play_macro = QPushButton("PLAY MACRO (F6)")
        self.btn_play_macro.setObjectName("PrimaryButton")
        self.btn_play_macro.setCursor(Qt.PointingHandCursor)
        self.btn_play_macro.setMinimumHeight(52)
        self.btn_play_macro.clicked.connect(self.toggle_playback)
        play_row.addWidget(self.btn_play_macro, stretch=1)
        layout.addLayout(play_row)

    def clear_macro(self):
        if self.recorder.recording or self.is_playing:
            return
        self.recorder.events = []
        self.list_events.clear()
        self.lbl_rec_status.setText("●  Cleared (0 events)")
        self.lbl_rec_status.setStyleSheet("color: #94A3B8;")

    def toggle_recording(self):
        if not self.recorder.recording:
            self.recorder.start()
            self.recording_changed.emit(True)
        else:
            self.recorder.stop(remove_last_click=True)
            self.refresh_rec_list()
            self.recording_changed.emit(False)

    def toggle_playback(self):
        if self.is_playing:
            self.stop_playback()
        else:
            self.start_playback()

    def start_playback(self):
        if self.is_playing or not self.recorder.events:
            return
        self.stop_event.clear()

        speed = self.slider_speed.value() / 10.0
        smart_move = self.chk_straight_line.isChecked()
        repeat_count = self.spin_macro_repeat.value()
        self.player_thread = MacroPlayerThread(
            self.recorder.events,
            speed,
            self.stop_event,
            smart_move=smart_move,
            repeat_count=repeat_count,
        )
        self.player_thread.finished.connect(self.on_playback_finished)
        self.player_thread.start()

        self.status_changed.emit(True)

    def stop_playback(self):
        if not self.is_playing:
            return
        self.stop_event.set()
        self.status_changed.emit(False)

    def on_playback_finished(self):
        self.status_changed.emit(False)

    def set_hotkey_labels(self, start_key: str, rec_key: str):
        self._start_hotkey_label = start_key.upper()
        self._rec_hotkey_label = rec_key.upper()
        self.update_playback_ui(self.is_playing)
        if not self.recorder.recording:
            self.btn_rec.setText(f"⏺️  RECORD ({self._rec_hotkey_label})")

    def update_recording_ui(self, is_recording: bool):
        rk = self._rec_hotkey_label
        if is_recording:
            self.btn_rec.setText(f"⏹️  STOP RECORDING ({rk})")
            self.lbl_rec_status.setText(f"🔴  Recording... (Press {rk} to Stop)")
            self.lbl_rec_status.setStyleSheet("color: #EF4444; font-weight: 700;")
            self.btn_play_macro.setEnabled(False)
        else:
            self.btn_rec.setText(f"⏺️  RECORD ({rk})")
            count = len(self.recorder.events)
            self.lbl_rec_status.setText(f"✓  Recorded {count} events")
            self.lbl_rec_status.setStyleSheet("color: #10B981; font-weight: 700;")
            self.btn_play_macro.setEnabled(True)

    def update_playback_ui(self, is_playing: bool):
        self.is_playing = is_playing
        sk = self._start_hotkey_label
        if is_playing:
            self.btn_play_macro.setText(f"STOP PLAYBACK ({sk})")
            self.btn_play_macro.setObjectName("DangerButton")
            self.btn_rec.setEnabled(False)
            self.spin_macro_repeat.setEnabled(False)
        else:
            self.btn_play_macro.setText(f"PLAY MACRO ({sk})")
            self.btn_play_macro.setObjectName("PrimaryButton")
            self.btn_rec.setEnabled(True)
            self.spin_macro_repeat.setEnabled(True)

        self.btn_play_macro.style().unpolish(self.btn_play_macro)
        self.btn_play_macro.style().polish(self.btn_play_macro)

    def refresh_rec_list(self):
        self.list_events.setUpdatesEnabled(False)
        self.list_events.clear()
        items = []
        for i, ev in enumerate(self.recorder.events):
            ev_type = ev.get('type')
            if ev_type == 'move':
                continue

            ts = ev.get('time', 0.0)
            info = f"[{ts:6.2f}s]  #{i:03d}  —  "
            if ev_type == 'click':
                action = 'Down' if ev.get('pressed') else 'Up'
                info += f"🖱️ Click {ev.get('button')} {action} at ({ev.get('x')}, {ev.get('y')})"
            elif ev_type == 'key_press':
                info += f"⌨️ Key Down: {ev.get('key')}"
            elif ev_type == 'key_release':
                info += f"⌨️ Key Up:   {ev.get('key')}"
            elif ev_type == 'scroll':
                info += f"🖱️ Scroll at ({ev.get('x')}, {ev.get('y')}) Δ({ev.get('dx')}, {ev.get('dy')})"
            items.append(info)

        if items:
            self.list_events.addItems(items)
            self.list_events.scrollToBottom()
        self.list_events.setUpdatesEnabled(True)

    def save_macro(self):
        if not self.recorder.events:
            return
        f, _ = QFileDialog.getSaveFileName(self, "Save Macro", "", "JSON (*.json)")
        if f:
            with open(f, 'w') as file:
                json.dump(self.recorder.events, file, indent=2)
            self.lbl_rec_status.setText(f"💾  Saved ({len(self.recorder.events)} events)")

    def load_macro(self):
        f, _ = QFileDialog.getOpenFileName(self, "Load Macro", "", "JSON (*.json)")
        if f:
            with open(f, 'r') as file:
                self.recorder.events = json.load(file)
                self.refresh_rec_list()
                self.lbl_rec_status.setText(f"📂  Loaded {len(self.recorder.events)} events")
                self.lbl_rec_status.setStyleSheet("color: #38BDF8; font-weight: 700;")

    @Slot()
    def toggle_clicking(self):
        """Called by F6 hotkey."""
        self.toggle_playback()

    @Slot()
    def toggle_recording_hotkey(self):
        """Called by F7 hotkey."""
        self.toggle_recording()
