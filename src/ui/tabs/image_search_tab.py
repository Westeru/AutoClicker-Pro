import os
import threading
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QDoubleSpinBox, QCheckBox, QFileDialog,
    QGroupBox, QFrame, QProgressBar
)
from PySide6.QtGui import QPixmap
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
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(18)

        # --- Page Header ---
        header_col = QVBoxLayout()
        header_col.setSpacing(2)
        title = QLabel("Image Search Autoclicker")
        title.setObjectName("HeaderLabel")
        header_col.addWidget(title)

        subtitle = QLabel("Automatically detect and click on-screen visual targets using OpenCV template matching")
        subtitle.setObjectName("PageSubtitle")
        header_col.addWidget(subtitle)
        layout.addLayout(header_col)

        # --- Target Image Selection & Preview Card ---
        target_group = QGroupBox("TARGET TEMPLATE IMAGE")
        target_layout = QVBoxLayout(target_group)
        target_layout.setSpacing(12)

        row1 = QHBoxLayout()
        row1.setSpacing(10)
        self.line_img_path = QLineEdit()
        self.line_img_path.setPlaceholderText("Select a target image snippet (*.png, *.jpg, *.jpeg)...")
        self.line_img_path.textChanged.connect(self._update_image_preview)
        row1.addWidget(self.line_img_path, stretch=1)

        self.btn_browse = QPushButton("📂  Browse...")
        self.btn_browse.setCursor(Qt.PointingHandCursor)
        self.btn_browse.clicked.connect(self.browse_image)
        row1.addWidget(self.btn_browse)
        target_layout.addLayout(row1)

        # Preview Box
        preview_frame = QFrame()
        preview_frame.setObjectName("SubCard")
        preview_frame.setMinimumHeight(96)
        preview_layout = QHBoxLayout(preview_frame)
        preview_layout.setContentsMargins(14, 10, 14, 10)

        self.lbl_preview = QLabel("No template selected — choose a cropped screenshot of the button or icon to click.")
        self.lbl_preview.setAlignment(Qt.AlignCenter)
        self.lbl_preview.setObjectName("FieldLabel")
        preview_layout.addWidget(self.lbl_preview, stretch=1)

        self.lbl_img_meta = QLabel("")
        self.lbl_img_meta.setObjectName("BadgeLabel")
        self.lbl_img_meta.setVisible(False)
        preview_layout.addWidget(self.lbl_img_meta, alignment=Qt.AlignVCenter)

        target_layout.addWidget(preview_frame)
        layout.addWidget(target_group)

        # --- Middle Row: Detection Parameters & Live Telemetry ---
        mid_row = QHBoxLayout()
        mid_row.setSpacing(16)

        # 1. Detection Parameters Card
        params_group = QGroupBox("DETECTION PARAMETERS")
        form_layout = QVBoxLayout(params_group)
        form_layout.setSpacing(12)

        h1 = QHBoxLayout()
        h1.addWidget(QLabel("Match Confidence Threshold:", objectName="SectionLabel"))
        self.spin_conf = QDoubleSpinBox()
        self.spin_conf.setRange(0.1, 1.0)
        self.spin_conf.setSingleStep(0.05)
        self.spin_conf.setValue(0.8)
        self.spin_conf.setDecimals(2)
        h1.addWidget(self.spin_conf)
        form_layout.addLayout(h1)

        h2 = QHBoxLayout()
        h2.addWidget(QLabel("Scan Interval:", objectName="SectionLabel"))
        self.spin_img_interval = QDoubleSpinBox()
        self.spin_img_interval.setRange(0.05, 60.0)
        self.spin_img_interval.setValue(1.0)
        self.spin_img_interval.setSingleStep(0.25)
        self.spin_img_interval.setSuffix(" s")
        h2.addWidget(self.spin_img_interval)
        form_layout.addLayout(h2)

        self.chk_gray = QCheckBox("Grayscale Matching (3× faster & more resilient to color shifts)")
        self.chk_gray.setChecked(True)
        form_layout.addWidget(self.chk_gray)
        form_layout.addStretch()

        mid_row.addWidget(params_group, stretch=3)

        # 2. Live Telemetry Card
        telemetry_group = QGroupBox("LIVE TELEMETRY")
        telemetry_layout = QVBoxLayout(telemetry_group)
        telemetry_layout.setSpacing(10)

        self.lbl_match_info = QLabel("Last Confidence: N/A")
        self.lbl_match_info.setStyleSheet("font-size: 15px; color: #94A3B8; font-weight: 700;")
        telemetry_layout.addWidget(self.lbl_match_info)

        self.conf_progress = QProgressBar()
        self.conf_progress.setRange(0, 100)
        self.conf_progress.setValue(0)
        telemetry_layout.addWidget(self.conf_progress)

        self.lbl_telemetry_hint = QLabel("Waiting for scanner to start...")
        self.lbl_telemetry_hint.setObjectName("PageSubtitle")
        telemetry_layout.addWidget(self.lbl_telemetry_hint)
        telemetry_layout.addStretch()

        mid_row.addWidget(telemetry_group, stretch=2)
        layout.addLayout(mid_row)

        layout.addStretch()

        # --- Start Button ---
        self.btn_start_img = QPushButton("START SEARCH (F6)")
        self.btn_start_img.setObjectName("PrimaryButton")
        self.btn_start_img.setCursor(Qt.PointingHandCursor)
        self.btn_start_img.setMinimumHeight(52)
        self.btn_start_img.clicked.connect(self.toggle_clicking)
        layout.addWidget(self.btn_start_img)

    def _update_image_preview(self, path: str):
        path = path.strip()
        if path and os.path.isfile(path):
            pix = QPixmap(path)
            if not pix.isNull():
                scaled = pix.scaled(220, 72, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                self.lbl_preview.setPixmap(scaled)
                self.lbl_img_meta.setText(f"{pix.width()} × {pix.height()} px")
                self.lbl_img_meta.setVisible(True)
                return
        self.lbl_preview.setPixmap(QPixmap())
        self.lbl_preview.setText("No valid image preview available.")
        self.lbl_img_meta.setVisible(False)

    def browse_image(self):
        f, _ = QFileDialog.getOpenFileName(self, "Select Image", "", "Images (*.png *.jpg *.jpeg)")
        if f:
            self.line_img_path.setText(f)

    @Slot()
    def toggle_clicking(self):
        if self.is_running:
            self.stop_search()
        else:
            self.start_search()

    def start_search(self):
        path = self.line_img_path.text().strip()
        if not path or self.is_running:
            return

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

        self.lbl_telemetry_hint.setText("Scanning screen for target...")
        self.status_changed.emit(True)

    def stop_search(self):
        if not self.is_running:
            return
        self.stop_event.set()
        self.lbl_telemetry_hint.setText("Scanner stopped.")
        self.status_changed.emit(False)

    def on_confidence_update(self, conf: float):
        threshold = self.spin_conf.value()
        matched = conf >= threshold
        color = "#10B981" if matched else "#F59E0B" if conf >= threshold * 0.8 else "#EF4444"
        self.lbl_match_info.setText(f"Last Confidence: {conf:.2f}")
        self.lbl_match_info.setStyleSheet(f"font-size: 15px; font-weight: 700; color: {color};")
        self.conf_progress.setValue(int(max(0.0, min(1.0, conf)) * 100))
        if matched:
            self.lbl_telemetry_hint.setText("Target matched & clicked!")
        else:
            self.lbl_telemetry_hint.setText(f"Below threshold ({threshold:.2f})")

    def on_thread_finished(self):
        self.status_changed.emit(False)

    def update_ui_state(self, is_running: bool):
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
        self.btn_browse.setEnabled(not is_running)
        self.spin_conf.setEnabled(not is_running)
        self.spin_img_interval.setEnabled(not is_running)
        self.chk_gray.setEnabled(not is_running)
