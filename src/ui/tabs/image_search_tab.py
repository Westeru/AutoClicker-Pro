import os
import threading
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QDoubleSpinBox, QCheckBox, QFileDialog,
    QGroupBox, QFrame, QProgressBar, QComboBox, QApplication
)
from PySide6.QtGui import QPixmap, QKeySequence, QShortcut
from PySide6.QtCore import Qt, Signal, QThread, Slot, QTimer
from src.vision import ImageSearcher
from src.screen_utils import get_monitors, save_qimage_snip
from src.ui.snip_overlay import SnipOverlay


class VisionThread(QThread):
    finished = Signal()
    error = Signal(str)
    confidence_update = Signal(float)
    clicked = Signal()

    def __init__(self, searcher_instance, config):
        super().__init__()
        self.searcher = searcher_instance
        self.config = config
        self.searcher.update_callback = self.emit_confidence
        self.searcher.on_click_callback = self.clicked.emit

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
    action_performed = Signal()

    def __init__(self, settings_manager=None):
        super().__init__()

        self.settings = settings_manager
        self.searcher = None
        self.vision_thread = None
        self.stop_event = threading.Event()
        self.is_running = False
        self._monitors = []
        self._snip_overlay = None
        self._roi_rect = None
        self._hotkey_label = "F6"

        self.setup_ui()
        self.refresh_monitors()
        if self.settings is not None:
            self._load_saved_state()
        self.status_changed.connect(self.update_ui_state)

        # Allow Ctrl+V anywhere in this tab to paste a snipped image directly
        self._paste_shortcut = QShortcut(QKeySequence.Paste, self)
        self._paste_shortcut.setContext(Qt.WidgetWithChildrenShortcut)
        self._paste_shortcut.activated.connect(self._handle_paste_shortcut)

    def set_hotkey_label(self, key_label: str):
        self._hotkey_label = key_label.upper()
        self.update_ui_state(self.is_running)

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)

        # --- Page Header ---
        header_col = QVBoxLayout()
        header_col.setSpacing(2)
        title = QLabel("Image Search Autoclicker")
        title.setObjectName("HeaderLabel")
        header_col.addWidget(title)

        subtitle = QLabel("Snip, paste (Ctrl+V), or browse a target image and choose a monitor or custom ROI")
        subtitle.setObjectName("PageSubtitle")
        header_col.addWidget(subtitle)
        layout.addLayout(header_col)

        # --- Target Image Selection & Preview Card ---
        target_group = QGroupBox("TARGET TEMPLATE IMAGE")
        target_layout = QVBoxLayout(target_group)
        target_layout.setSpacing(10)

        row1 = QHBoxLayout()
        row1.setSpacing(8)
        self.line_img_path = QLineEdit()
        self.line_img_path.setPlaceholderText("Snip, Paste (Ctrl+V), or Browse an image (*.png, *.jpg)...")
        self.line_img_path.textChanged.connect(self._update_image_preview)
        row1.addWidget(self.line_img_path, stretch=1)

        self.btn_snip = QPushButton("✂️  Snip")
        self.btn_snip.setObjectName("SuccessButton")
        self.btn_snip.setCursor(Qt.PointingHandCursor)
        self.btn_snip.setToolTip("Capture a target image directly from any monitor")
        self.btn_snip.clicked.connect(self.start_snip)
        row1.addWidget(self.btn_snip)

        self.btn_paste = QPushButton("📋  Paste")
        self.btn_paste.setCursor(Qt.PointingHandCursor)
        self.btn_paste.setToolTip("Paste image from clipboard (Ctrl+V)")
        self.btn_paste.clicked.connect(self.paste_from_clipboard)
        row1.addWidget(self.btn_paste)

        self.btn_browse = QPushButton("📂  Browse")
        self.btn_browse.setCursor(Qt.PointingHandCursor)
        self.btn_browse.clicked.connect(self.browse_image)
        row1.addWidget(self.btn_browse)
        target_layout.addLayout(row1)

        # Preview Box
        preview_frame = QFrame()
        preview_frame.setObjectName("SubCard")
        preview_frame.setMinimumHeight(86)
        preview_layout = QHBoxLayout(preview_frame)
        preview_layout.setContentsMargins(14, 8, 14, 8)

        self.lbl_preview = QLabel("Press Ctrl+V to paste a snip, click ✂️ Snip, or Browse an image file.")
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
        mid_row.setSpacing(14)

        # 1. Detection Parameters Card
        params_group = QGroupBox("DETECTION PARAMETERS")
        form_layout = QVBoxLayout(params_group)
        form_layout.setSpacing(8)

        # Monitor Selection Row
        h_mon = QHBoxLayout()
        h_mon.setSpacing(6)
        h_mon.addWidget(QLabel("Target Monitor:", objectName="SectionLabel"))
        self.combo_monitor = QComboBox()
        self.combo_monitor.setToolTip("Select which monitor to search and click on")
        h_mon.addWidget(self.combo_monitor, stretch=1)

        self.btn_refresh_mon = QPushButton("↻")
        self.btn_refresh_mon.setFixedSize(36, 34)
        self.btn_refresh_mon.setStyleSheet("padding: 0px; font-size: 16px;")
        self.btn_refresh_mon.setCursor(Qt.PointingHandCursor)
        self.btn_refresh_mon.setToolTip("Refresh connected monitors")
        self.btn_refresh_mon.clicked.connect(self.refresh_monitors)
        h_mon.addWidget(self.btn_refresh_mon)
        form_layout.addLayout(h_mon)

        # Search Region (ROI) Row
        h_roi = QHBoxLayout()
        h_roi.setSpacing(6)
        h_roi.addWidget(QLabel("Search Region:", objectName="SectionLabel"))
        self.lbl_roi_status = QLabel("Full Monitor")
        self.lbl_roi_status.setObjectName("BadgeLabel")
        h_roi.addWidget(self.lbl_roi_status)
        h_roi.addStretch()

        self.btn_set_roi = QPushButton("📐 Set Region")
        self.btn_set_roi.setCursor(Qt.PointingHandCursor)
        self.btn_set_roi.setToolTip("Draw a smaller search box for 5–10× faster scanning & zero false clicks")
        self.btn_set_roi.clicked.connect(self.start_roi_selection)
        h_roi.addWidget(self.btn_set_roi)

        self.btn_clear_roi = QPushButton("✕")
        self.btn_clear_roi.setFixedSize(32, 32)
        self.btn_clear_roi.setStyleSheet("padding: 0px;")
        self.btn_clear_roi.setToolTip("Clear custom search region (scan full monitor)")
        self.btn_clear_roi.setCursor(Qt.PointingHandCursor)
        self.btn_clear_roi.setVisible(False)
        self.btn_clear_roi.clicked.connect(self.clear_roi)
        h_roi.addWidget(self.btn_clear_roi)
        form_layout.addLayout(h_roi)

        # Confidence, Interval & Cooldown Row
        h_nums = QHBoxLayout()
        h_nums.setSpacing(10)

        h_nums.addWidget(QLabel("Confidence:", objectName="FieldLabel"))
        self.spin_conf = QDoubleSpinBox()
        self.spin_conf.setRange(0.1, 1.0)
        self.spin_conf.setSingleStep(0.05)
        self.spin_conf.setValue(0.8)
        self.spin_conf.setDecimals(2)
        h_nums.addWidget(self.spin_conf)

        h_nums.addWidget(QLabel("Scan:", objectName="FieldLabel"))
        self.spin_img_interval = QDoubleSpinBox()
        self.spin_img_interval.setRange(0.05, 60.0)
        self.spin_img_interval.setValue(1.0)
        self.spin_img_interval.setSingleStep(0.25)
        self.spin_img_interval.setSuffix(" s")
        h_nums.addWidget(self.spin_img_interval)

        h_nums.addWidget(QLabel("Cooldown:", objectName="FieldLabel"))
        self.spin_cooldown = QDoubleSpinBox()
        self.spin_cooldown.setRange(0.0, 300.0)
        self.spin_cooldown.setValue(0.0)
        self.spin_cooldown.setSingleStep(0.5)
        self.spin_cooldown.setSuffix(" s")
        self.spin_cooldown.setToolTip("Extra pause after a successful click to avoid double-clicking fading buttons")
        h_nums.addWidget(self.spin_cooldown)
        form_layout.addLayout(h_nums)

        self.chk_gray = QCheckBox("Grayscale Matching (3× faster & more resilient to color shifts)")
        self.chk_gray.setChecked(True)
        form_layout.addWidget(self.chk_gray)

        self.chk_return_cursor = QCheckBox("Return mouse to original position after click")
        self.chk_return_cursor.setChecked(True)
        form_layout.addWidget(self.chk_return_cursor)
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
        self.lbl_telemetry_hint.setWordWrap(True)
        telemetry_layout.addWidget(self.lbl_telemetry_hint)
        telemetry_layout.addStretch()

        mid_row.addWidget(telemetry_group, stretch=2)
        layout.addLayout(mid_row)

        layout.addStretch()

        # --- Start Button ---
        self.btn_start_img = QPushButton("START SEARCH (F6)")
        self.btn_start_img.setObjectName("PrimaryButton")
        self.btn_start_img.setCursor(Qt.PointingHandCursor)
        self.btn_start_img.setMinimumHeight(50)
        self.btn_start_img.clicked.connect(self.toggle_clicking)
        layout.addWidget(self.btn_start_img)

    # --- SETTINGS ---
    def _load_saved_state(self):
        state = self.settings.get("last_vision_state")
        if not isinstance(state, dict):
            return
        self.spin_conf.setValue(float(state.get("confidence", 0.8)))
        self.spin_img_interval.setValue(float(state.get("interval", 1.0)))
        self.spin_cooldown.setValue(float(state.get("cooldown", 0.0)))
        self.chk_gray.setChecked(bool(state.get("grayscale", True)))
        self.chk_return_cursor.setChecked(bool(state.get("return_cursor", True)))
        mon_name = state.get("monitor_name", "")
        if mon_name:
            idx = self.combo_monitor.findText(mon_name)
            if idx >= 0:
                self.combo_monitor.setCurrentIndex(idx)

    def save_last_state(self):
        if self.settings is None:
            return
        self.settings.set("last_vision_state", {
            "confidence": self.spin_conf.value(),
            "interval": self.spin_img_interval.value(),
            "cooldown": self.spin_cooldown.value(),
            "grayscale": self.chk_gray.isChecked(),
            "return_cursor": self.chk_return_cursor.isChecked(),
            "monitor_name": self.combo_monitor.currentText(),
        })

    # --- MONITOR & ROI MANAGEMENT ---
    def refresh_monitors(self):
        prev_idx = self.combo_monitor.currentIndex()
        self._monitors = get_monitors()
        self.combo_monitor.clear()
        for mon in self._monitors:
            self.combo_monitor.addItem(mon["name"], mon["rect"])
        if 0 <= prev_idx < self.combo_monitor.count():
            self.combo_monitor.setCurrentIndex(prev_idx)
        elif self.combo_monitor.count() > 1:
            self.combo_monitor.setCurrentIndex(0)

    def get_selected_monitor_rect(self):
        return self.combo_monitor.currentData()

    def start_roi_selection(self):
        if self.is_running:
            return
        top_win = self.window()
        if top_win and top_win.isVisible():
            top_win.hide()
        QTimer.singleShot(180, self._launch_roi_overlay)

    def _launch_roi_overlay(self):
        self._snip_overlay = SnipOverlay()
        self._snip_overlay.snip_rect_captured.connect(self._on_roi_captured)
        self._snip_overlay.snip_cancelled.connect(self._on_snip_cancelled)
        self._snip_overlay.start_snip()

    def _on_roi_captured(self, rect_tuple: tuple):
        self._restore_window()
        self._roi_rect = rect_tuple
        w = rect_tuple[2] - rect_tuple[0]
        h = rect_tuple[3] - rect_tuple[1]
        self.lbl_roi_status.setText(f"ROI: {w}×{h} @ ({rect_tuple[0]}, {rect_tuple[1]})")
        self.btn_clear_roi.setVisible(True)
        self.lbl_telemetry_hint.setText(f"Search restricted to {w}×{h} px region!")

    def clear_roi(self):
        self._roi_rect = None
        self.lbl_roi_status.setText("Full Monitor")
        self.btn_clear_roi.setVisible(False)
        self.lbl_telemetry_hint.setText("Search region cleared (scanning full selected monitor).")

    # --- SNIP & PASTE ---
    def _handle_paste_shortcut(self):
        clipboard = QApplication.clipboard()
        if clipboard.mimeData() and clipboard.mimeData().hasImage():
            self.paste_from_clipboard()
        elif self.line_img_path.hasFocus():
            self.line_img_path.paste()

    def paste_from_clipboard(self) -> bool:
        if self.is_running:
            return False
        clipboard = QApplication.clipboard()
        image = clipboard.image()
        if image is None or image.isNull():
            self.lbl_telemetry_hint.setText("Clipboard has no image — take a snip (Win+Shift+S or ✂️ Snip) first.")
            return False

        saved_path = save_qimage_snip(image, prefix="pasted")
        if saved_path:
            self.line_img_path.setText(saved_path)
            self.lbl_telemetry_hint.setText(f"Pasted snip ({image.width()}×{image.height()} px) ready!")
            return True
        return False

    def start_snip(self):
        if self.is_running:
            return
        top_win = self.window()
        if top_win and top_win.isVisible():
            top_win.hide()
        QTimer.singleShot(180, self._launch_snip_overlay)

    def _launch_snip_overlay(self):
        self._snip_overlay = SnipOverlay()
        self._snip_overlay.snip_captured.connect(self._on_snip_captured)
        self._snip_overlay.snip_cancelled.connect(self._on_snip_cancelled)
        self._snip_overlay.start_snip()

    def _restore_window(self):
        top_win = self.window()
        if top_win:
            top_win.show()
            top_win.raise_()
            top_win.activateWindow()

    def _on_snip_captured(self, pixmap: QPixmap):
        self._restore_window()
        saved_path = save_qimage_snip(pixmap, prefix="snip")
        if saved_path:
            self.line_img_path.setText(saved_path)
            self.lbl_telemetry_hint.setText(f"Captured snip ({pixmap.width()}×{pixmap.height()} px) ready!")

    def _on_snip_cancelled(self):
        self._restore_window()
        self.lbl_telemetry_hint.setText("Selection cancelled.")

    def _update_image_preview(self, path: str):
        path = path.strip()
        if path and os.path.isfile(path):
            pix = QPixmap(path)
            if not pix.isNull():
                scaled = pix.scaled(220, 68, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                self.lbl_preview.setPixmap(scaled)
                self.lbl_img_meta.setText(f"{pix.width()} × {pix.height()} px")
                self.lbl_img_meta.setVisible(True)
                return
        self.lbl_preview.setPixmap(QPixmap())
        self.lbl_preview.setText("Press Ctrl+V to paste a snip, click ✂️ Snip, or Browse an image file.")
        self.lbl_img_meta.setVisible(False)

    def browse_image(self):
        f, _ = QFileDialog.getOpenFileName(self, "Select Image", "", "Images (*.png *.jpg *.jpeg)")
        if f:
            self.line_img_path.setText(f)

    # --- SEARCH CONTROL ---
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

        self.save_last_state()
        config = {
            'img_path': path,
            'interval': self.spin_img_interval.value(),
            'confidence': self.spin_conf.value(),
            'grayscale': self.chk_gray.isChecked(),
            'monitor_rect': self.get_selected_monitor_rect(),
            'roi_rect': self._roi_rect,
            'return_cursor': self.chk_return_cursor.isChecked(),
            'cooldown': self.spin_cooldown.value(),
        }

        self.stop_event.clear()
        self.searcher = ImageSearcher(self.stop_event, update_callback=None)

        self.vision_thread = VisionThread(self.searcher, config)
        self.vision_thread.confidence_update.connect(self.on_confidence_update)
        self.vision_thread.clicked.connect(self.action_performed.emit)
        self.vision_thread.finished.connect(self.on_thread_finished)
        self.vision_thread.start()

        target_desc = self.lbl_roi_status.text() if self._roi_rect else self.combo_monitor.currentText()
        self.lbl_telemetry_hint.setText(f"Scanning {target_desc}...")
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
        hk = self._hotkey_label
        if is_running:
            self.btn_start_img.setText(f"STOP SEARCH ({hk})")
            self.btn_start_img.setObjectName("DangerButton")
        else:
            self.btn_start_img.setText(f"START SEARCH ({hk})")
            self.btn_start_img.setObjectName("PrimaryButton")

        self.btn_start_img.style().unpolish(self.btn_start_img)
        self.btn_start_img.style().polish(self.btn_start_img)

        self.line_img_path.setEnabled(not is_running)
        self.btn_browse.setEnabled(not is_running)
        self.btn_snip.setEnabled(not is_running)
        self.btn_paste.setEnabled(not is_running)
        self.combo_monitor.setEnabled(not is_running)
        self.btn_refresh_mon.setEnabled(not is_running)
        self.btn_set_roi.setEnabled(not is_running)
        self.btn_clear_roi.setEnabled(not is_running)
        self.spin_conf.setEnabled(not is_running)
        self.spin_img_interval.setEnabled(not is_running)
        self.spin_cooldown.setEnabled(not is_running)
        self.chk_gray.setEnabled(not is_running)
        self.chk_return_cursor.setEnabled(not is_running)
