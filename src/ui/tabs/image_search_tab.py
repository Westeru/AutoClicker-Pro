import threading
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, 
    QPushButton, QDoubleSpinBox, QCheckBox, QFileDialog
)
from PySide6.QtCore import Qt, Signal, QThread, Slot
from src.vision import ImageSearcher

class VisionThread(QThread):
    finished = Signal()
    error = Signal(str)
    confidence_update = Signal(float)

    def __init__(self, searcher_instance, config):
        super().__init__()
        self.searcher = searcher_instance
        self.config = config
        # Wire backend callback to Qt Signal
        self.searcher.update_callback = self.emit_confidence

    def emit_confidence(self, conf):
        self.confidence_update.emit(conf)

    def run(self):
        try:
            self.searcher.run(self.config)
        except Exception as e:
            self.error.emit(str(e))
        finally:
            self.finished.emit()

class ImageSearchTab(QWidget):
    status_changed = Signal(bool)

    def __init__(self):
        super().__init__()

        self.searcher = None
        self.vision_thread = None
        self.stop_event = threading.Event()
        self.is_running = False

        self.setup_ui()
        self.status_changed.connect(self.update_ui_state)

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        title = QLabel("Image Search Autoclicker")
        title.setObjectName("HeaderLabel")
        layout.addWidget(title)

        # Target Selection
        layout.addWidget(QLabel("Target Image:", objectName="SectionLabel"))
        
        row1 = QHBoxLayout()
        self.line_img_path = QLineEdit()
        self.line_img_path.setPlaceholderText("Path to snippet image (*.png, *.jpg)...")
        row1.addWidget(self.line_img_path)
        
        btn_browse = QPushButton("Browse")
        btn_browse.clicked.connect(self.browse_image)
        row1.addWidget(btn_browse)
        layout.addLayout(row1)

        # Settings Form
        form_layout = QVBoxLayout()
        
        h1 = QHBoxLayout()
        h1.addWidget(QLabel("Match Confidence:"))
        self.spin_conf = QDoubleSpinBox()
        self.spin_conf.setRange(0.1, 1.0)
        self.spin_conf.setSingleStep(0.05)
        self.spin_conf.setValue(0.8)
        self.spin_conf.setDecimals(2)
        h1.addWidget(self.spin_conf)
        form_layout.addLayout(h1)
        
        h2 = QHBoxLayout()
        h2.addWidget(QLabel("Check Interval (s):"))
        self.spin_img_interval = QDoubleSpinBox()
        self.spin_img_interval.setRange(0.1, 60.0)
        self.spin_img_interval.setValue(1.0)
        self.spin_img_interval.setSingleStep(0.5)
        h2.addWidget(self.spin_img_interval)
        form_layout.addLayout(h2)
        
        self.chk_gray = QCheckBox("Use Grayscale (Faster & more reliable usually)")
        self.chk_gray.setChecked(True)
        form_layout.addWidget(self.chk_gray)
        
        layout.addLayout(form_layout)
        
        # Real-time feedback
        self.lbl_match_info = QLabel("Last Confidence: N/A")
        self.lbl_match_info.setStyleSheet("font-size: 14px; color: #10B981; font-weight: bold;") 
        layout.addWidget(self.lbl_match_info)

        layout.addStretch()

        # Start Button
        self.btn_start_img = QPushButton("START SEARCH (F6)")
        self.btn_start_img.setObjectName("PrimaryButton")
        self.btn_start_img.setMinimumHeight(50)
        self.btn_start_img.clicked.connect(self.toggle_clicking)
        layout.addWidget(self.btn_start_img)

    def browse_image(self):
        f, _ = QFileDialog.getOpenFileName(self, "Select Image", "", "Images (*.png *.jpg *.jpeg)")
        if f:
            self.line_img_path.setText(f)

    @Slot()
    def toggle_clicking(self):
        # Tied to the global F6 hotkey logic
        if self.is_running:
            self.stop_search()
        else:
            self.start_search()

    def start_search(self):
        path = self.line_img_path.text()
        if not path or self.is_running: return
        
        config = {
            'img_path': path,
            'interval': self.spin_img_interval.value(),
            'confidence': self.spin_conf.value(),
            'grayscale': self.chk_gray.isChecked()
        }

        self.stop_event.clear()
        self.searcher = ImageSearcher(self.stop_event, update_callback=None) 
        
        self.vision_thread = VisionThread(self.searcher, config)
        self.vision_thread.confidence_update.connect(self.on_confidence_update)
        self.vision_thread.finished.connect(self.on_thread_finished)
        self.vision_thread.start()

        self.status_changed.emit(True)

    def stop_search(self):
        if not self.is_running: return
        self.stop_event.set()
        self.status_changed.emit(False)

    def on_confidence_update(self, conf):
        color = "#10B981" if conf >= self.spin_conf.value() else "#EF4444"
        self.lbl_match_info.setText(f"Last Confidence: {conf:.2f}")
        self.lbl_match_info.setStyleSheet(f"font-size: 14px; font-weight: bold; color: {color};")

    def on_thread_finished(self):
        self.status_changed.emit(False)

    def update_ui_state(self, is_running):
        self.is_running = is_running
        if is_running:
            self.btn_start_img.setText("STOP SEARCH (F6)")
            self.btn_start_img.setObjectName("DangerButton")
        else:
            self.btn_start_img.setText("START SEARCH (F6)")
            self.btn_start_img.setObjectName("PrimaryButton")
            
        self.btn_start_img.style().unpolish(self.btn_start_img)
        self.btn_start_img.style().polish(self.btn_start_img)
        
        self.line_img_path.setEnabled(not is_running)
        self.spin_conf.setEnabled(not is_running)
        self.spin_img_interval.setEnabled(not is_running)
        self.chk_gray.setEnabled(not is_running)
