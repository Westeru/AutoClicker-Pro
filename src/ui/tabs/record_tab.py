import json
import threading
import time
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QCheckBox, 
    QSlider, QListWidget, QPushButton, QFileDialog
)
from PySide6.QtCore import Qt, Signal, QThread, Slot
from src.recorder import Recorder
from pynput.mouse import Button, Controller as MouseController
from pynput.keyboard import Controller as KeyboardController

class MacroPlayerThread(QThread):
    finished = Signal()
    error = Signal(str)

    def __init__(self, events, speed_multiplier, stop_event):
        super().__init__()
        self.events = events
        self.speed = speed_multiplier
        self.stop_event = stop_event
        self.mouse = MouseController()
        self.keyboard = KeyboardController()

    def run(self):
        try:
            if not self.events: return
            
            last_time = self.events[0]['time']
            for ev in self.events:
                if self.stop_event.is_set(): break
                
                delay = ev['time'] - last_time
                if delay > 0: 
                    time.sleep(delay / self.speed)
                last_time = ev['time']
                
                if self.stop_event.is_set(): break
                
                if ev['type'] == 'move':
                    self.mouse.position = (ev['x'], ev['y'])
                elif ev['type'] == 'click':
                    self.mouse.position = (ev['x'], ev['y'])
                    btn = getattr(Button, ev['button'], Button.left)
                    if ev.get('pressed', False): 
                        self.mouse.press(btn)
                    else: 
                        self.mouse.release(btn)
                elif ev['type'] == 'scroll':
                    self.mouse.position = (ev['x'], ev['y'])
                    self.mouse.scroll(ev['dx'], ev['dy'])
                elif ev['type'] == 'key_press':
                    self.keyboard.press(ev['key'])
                elif ev['type'] == 'key_release':
                    self.keyboard.release(ev['key'])
                    
        except Exception as e:
            self.error.emit(str(e))
        finally:
            self.finished.emit()


class RecordTab(QWidget):
    status_changed = Signal(bool) # playing back
    recording_changed = Signal(bool) # active recording

    def __init__(self):
        super().__init__()
        
        self.recorder = Recorder()
        self.player_thread = None
        self.stop_event = threading.Event()
        
        self.is_playing = False
        
        self.setup_ui()
        self.status_changed.connect(self.update_playback_ui)
        self.recording_changed.connect(self.update_recording_ui)

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        title = QLabel("Macro Recorder")
        title.setObjectName("HeaderLabel")
        layout.addWidget(title)
        
        # Controls
        ctrl_layout = QHBoxLayout()
        self.btn_rec = QPushButton("RECORD (F7)")
        self.btn_rec.setObjectName("DangerButton")
        self.btn_rec.setMinimumHeight(40)
        self.btn_rec.clicked.connect(self.toggle_recording)
        ctrl_layout.addWidget(self.btn_rec)
        
        btn_save = QPushButton("Save")
        btn_save.clicked.connect(self.save_macro)
        ctrl_layout.addWidget(btn_save)
        
        btn_load = QPushButton("Load")
        btn_load.clicked.connect(self.load_macro)
        ctrl_layout.addWidget(btn_load)
        layout.addLayout(ctrl_layout)

        # Info
        self.lbl_rec_status = QLabel("Ready to Record")
        self.lbl_rec_status.setAlignment(Qt.AlignCenter)
        self.lbl_rec_status.setStyleSheet("font-size: 14px; color: #B0B0B0;")
        layout.addWidget(self.lbl_rec_status)

        # Options
        opts_layout = QHBoxLayout()
        self.chk_straight_line = QCheckBox("Global Smart Move") 
        self.chk_straight_line.setToolTip("Interpolate mouse movements into straight lines (Visual placeholder)")
        opts_layout.addWidget(self.chk_straight_line)
        
        opts_layout.addStretch()
        
        opts_layout.addWidget(QLabel("Playback Speed:"))
        self.slider_speed = QSlider(Qt.Horizontal)
        self.slider_speed.setRange(5, 50) # 0.5x to 5.0x
        self.slider_speed.setValue(10) # 1.0x
        self.slider_speed.setFixedWidth(150)
        self.lbl_speed_val = QLabel("1.0x")
        self.slider_speed.valueChanged.connect(lambda v: self.lbl_speed_val.setText(f"{v/10.0:.1f}x"))
        opts_layout.addWidget(self.slider_speed)
        opts_layout.addWidget(self.lbl_speed_val)
        
        layout.addLayout(opts_layout)

        # Event List Display
        self.list_events = QListWidget()
        layout.addWidget(self.list_events)

        # Play Button
        self.btn_play_macro = QPushButton("PLAY MACRO (F6)")
        self.btn_play_macro.setObjectName("PrimaryButton")
        self.btn_play_macro.setMinimumHeight(50)
        self.btn_play_macro.clicked.connect(self.toggle_playback)
        layout.addWidget(self.btn_play_macro)

    def toggle_recording(self):
        if not self.recorder.recording:
            # Start
            self.recorder.start()
            self.recording_changed.emit(True)
        else:
            self.recorder.stop(remove_last_click=True)
            self.refresh_rec_list()
            self.recording_changed.emit(False)
            
    def toggle_playback(self):
        # We overload F6 from main_window.py to call toggle_clicking on current tab
        if self.is_playing:
            self.stop_playback()
        else:
            self.start_playback()

    def start_playback(self):
        if self.is_playing or not self.recorder.events: return
        self.stop_event.clear()
        
        speed = self.slider_speed.value() / 10.0
        self.player_thread = MacroPlayerThread(self.recorder.events, speed, self.stop_event)
        self.player_thread.finished.connect(self.on_playback_finished)
        self.player_thread.start()
        
        self.status_changed.emit(True)

    def stop_playback(self):
        if not self.is_playing: return
        self.stop_event.set()
        self.status_changed.emit(False)

    def on_playback_finished(self):
        self.status_changed.emit(False)

    def update_recording_ui(self, is_recording):
        if is_recording:
            self.btn_rec.setText("STOP RECORDING (F7)")
            self.lbl_rec_status.setText("Recording... (Press F7 or Stop Recording)")
            self.lbl_rec_status.setStyleSheet("color: #EF4444; font-weight: bold;")
            self.btn_play_macro.setEnabled(False)
        else:
            self.btn_rec.setText("RECORD (F7)")
            count = len(self.recorder.events)
            self.lbl_rec_status.setText(f"Recorded {count} events ({count} operations)")
            self.lbl_rec_status.setStyleSheet("color: #10B981;") # green success
            self.btn_play_macro.setEnabled(True)
            
    def update_playback_ui(self, is_playing):
        self.is_playing = is_playing
        if is_playing:
            self.btn_play_macro.setText("STOP PLAYBACK (F6)")
            self.btn_play_macro.setObjectName("DangerButton")
            self.btn_rec.setEnabled(False)
        else:
            self.btn_play_macro.setText("PLAY MACRO (F6)")
            self.btn_play_macro.setObjectName("PrimaryButton")
            self.btn_rec.setEnabled(True)
            
        self.btn_play_macro.style().unpolish(self.btn_play_macro)
        self.btn_play_macro.style().polish(self.btn_play_macro)

    def refresh_rec_list(self):
        self.list_events.clear()
        for i, ev in enumerate(self.recorder.events):
            if ev['type'] == 'move': continue # Ignore spammy moves for visualization
            
            # Format visual log
            info = f"{i:03d}: "
            if ev['type'] == 'click':
                action = 'Down' if ev.get('pressed') else 'Up'
                info += f"Click {ev.get('button')} {action} at ({ev.get('x')}, {ev.get('y')})"
            elif ev['type'] == 'key_press':
                info += f"Key Press: {ev.get('key')}"
            elif ev['type'] == 'key_release':
                info += f"Key Release: {ev.get('key')}"
            elif ev['type'] == 'scroll':
                info += f"Scroll at ({ev.get('x')}, {ev.get('y')}) delta ({ev.get('dx')}, {ev.get('dy')})"
                
            self.list_events.addItem(info)
        self.list_events.scrollToBottom()

    def save_macro(self):
        if not self.recorder.events: return
        f, _ = QFileDialog.getSaveFileName(self, "Save Macro", "", "JSON (*.json)")
        if f:
            with open(f, 'w') as file: 
                json.dump(self.recorder.events, file, indent=2)
            self.lbl_rec_status.setText(f"Macro saved to {f}")
            
    def load_macro(self):
        f, _ = QFileDialog.getOpenFileName(self, "Load Macro", "", "JSON (*.json)")
        if f:
            with open(f, 'r') as file:
                self.recorder.events = json.load(file)
                self.refresh_rec_list()
                self.lbl_rec_status.setText(f"Loaded {len(self.recorder.events)} events from {f}")
                self.lbl_rec_status.setStyleSheet("color: #3B82F6;")

    # Interface used by main_window.py global hotkeys
    @Slot()
    def toggle_clicking(self):
        """Called by F6 hotkey."""
        self.toggle_playback()
        
    @Slot()
    def toggle_recording_hotkey(self):
        """Called by F7 hotkey."""
        self.toggle_recording()
