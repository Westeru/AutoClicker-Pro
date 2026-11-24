import json
import os
import threading
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QDoubleSpinBox, QFileDialog,
    QListWidget, QAbstractItemView, QSpinBox, QComboBox, QCheckBox,
    QFrame, QMessageBox, QListWidgetItem, QApplication, QTextEdit
)
from PySide6.QtGui import QKeySequence, QShortcut, QColor, QPixmap
from PySide6.QtCore import Qt, Signal, QThread, QTimer, Slot
from src.workflow_runner import WorkflowRunner
from src.screen_utils import get_monitors, save_qimage_snip
from src.ui.snip_overlay import SnipOverlay


class ReorderableListWidget(QListWidget):
    order_changed = Signal()
    delete_key_pressed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDragDropMode(QAbstractItemView.InternalMove)
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.setAcceptDrops(True)

    def dropEvent(self, event):
        super().dropEvent(event)
        self.order_changed.emit()

    def keyPressEvent(self, event):
        if event.matches(QKeySequence.Copy):
            pass
        elif event.matches(QKeySequence.Paste):
            pass
        elif event.key() == Qt.Key_Delete:
            self.delete_key_pressed.emit()
        else:
            super().keyPressEvent(event)


class WorkflowThread(QThread):
    finished = Signal()
    error = Signal(str)
    step_highlight = Signal(int)
    ai_debug = Signal(str)

    def __init__(self, runner_instance, steps):
        super().__init__()
        self.runner = runner_instance
        self.runner.set_steps(steps)
        self.runner.highlight_callback = self.step_highlight.emit
        self.runner.ai_debug_callback = self.ai_debug.emit

    def run(self):
        try:
            self.runner.run()
        except Exception as e:
            self.error.emit(str(e))
        finally:
            self.finished.emit()


class WorkflowTab(QWidget):
    status_changed = Signal(bool)

    def __init__(self):
        super().__init__()

        self.workflow_steps = []
        self.wf_selected_index = -1
        self.is_running = False

        self.stop_event = threading.Event()
        self.runner = WorkflowRunner(self.stop_event)
        self.worker_thread = None

        # Resolve settings path relative to project root (two levels up from this file)
        self._settings_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), '..', '..', '..', 'settings.json'
        )
        self._settings_path = os.path.normpath(self._settings_path)

        # Debounce timer for saving API key
        self._save_key_timer = QTimer(self)
        self._save_key_timer.setSingleShot(True)
        self._save_key_timer.setInterval(500)
        self._save_key_timer.timeout.connect(self._do_save_key)

        self.setup_ui()
        self.status_changed.connect(self.update_ui_state)

    def setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(18)

        # LEFT COLUMN: Playlist Card
        left_frame = QFrame()
        left_frame.setObjectName("Card")
        lf_layout = QVBoxLayout(left_frame)
        lf_layout.setContentsMargins(18, 18, 18, 18)
        lf_layout.setSpacing(12)

        header_left = QHBoxLayout()
        lbl_list = QLabel("Workflow Playlist")
        lbl_list.setObjectName("HeaderLabel")
        header_left.addWidget(lbl_list)
        header_left.addStretch()

        self.lbl_step_count = QLabel("0 steps")
        self.lbl_step_count.setObjectName("BadgeLabel")
        header_left.addWidget(self.lbl_step_count)
        lf_layout.addLayout(header_left)

        lbl_hint = QLabel("Drag to reorder • Double-click to edit • Ctrl+C / Ctrl+V to duplicate")
        lbl_hint.setObjectName("PageSubtitle")
        lf_layout.addWidget(lbl_hint)

        self.wf_list = ReorderableListWidget()
        self.wf_list.order_changed.connect(self.sync_wf_order)
        self.wf_list.delete_key_pressed.connect(self.del_wf_item)
        self.wf_list.itemDoubleClicked.connect(self.on_wf_item_select)
        lf_layout.addWidget(self.wf_list, stretch=1)

        # Shortcuts for Copy/Paste
        QShortcut(QKeySequence.Copy, self.wf_list, self.copy_wf_step)
        QShortcut(QKeySequence.Paste, self.wf_list, self.paste_wf_step)

        # Tools Row
        tools_layout = QHBoxLayout()
        tools_layout.setSpacing(8)
        btn_up = QPushButton("↑ Up")
        btn_up.setCursor(Qt.PointingHandCursor)
        btn_up.clicked.connect(lambda: self.move_wf_item(-1))

        btn_down = QPushButton("↓ Down")
        btn_down.setCursor(Qt.PointingHandCursor)
        btn_down.clicked.connect(lambda: self.move_wf_item(1))

        btn_del = QPushButton("✕ Delete")
        btn_del.setObjectName("DangerButton")
        btn_del.setCursor(Qt.PointingHandCursor)
        btn_del.clicked.connect(self.del_wf_item)

        tools_layout.addWidget(btn_up)
        tools_layout.addWidget(btn_down)
        tools_layout.addWidget(btn_del)
        lf_layout.addLayout(tools_layout)

        # Save/Load Flow Row
        sl_layout = QHBoxLayout()
        sl_layout.setSpacing(8)
        btn_s = QPushButton("💾 Save Flow")
        btn_s.setCursor(Qt.PointingHandCursor)
        btn_s.clicked.connect(self.save_workflow)

        btn_l = QPushButton("📂 Load Flow")
        btn_l.setCursor(Qt.PointingHandCursor)
        btn_l.clicked.connect(self.load_workflow)

        sl_layout.addWidget(btn_s)
        sl_layout.addWidget(btn_l)
        lf_layout.addLayout(sl_layout)

        # Run Workflow Button
        self.btn_start_wf = QPushButton("RUN WORKFLOW (F6)")
        self.btn_start_wf.setObjectName("PrimaryButton")
        self.btn_start_wf.setCursor(Qt.PointingHandCursor)
        self.btn_start_wf.setMinimumHeight(48)
        self.btn_start_wf.clicked.connect(self.toggle_clicking)
        lf_layout.addWidget(self.btn_start_wf)

        # Debug Panel (Hidden by default)
        self.debug_panel = QFrame()
        self.debug_panel.setVisible(False)
        dp_layout = QVBoxLayout(self.debug_panel)
        dp_layout.setContentsMargins(0, 8, 0, 0)
        dp_layout.setSpacing(4)

        lbl_debug = QLabel("AI Execution Log")
        lbl_debug.setObjectName("SectionLabel")
        dp_layout.addWidget(lbl_debug)

        self.txt_debug = QTextEdit()
        self.txt_debug.setReadOnly(True)
        self.txt_debug.setMaximumHeight(95)
        dp_layout.addWidget(self.txt_debug)

        lf_layout.addWidget(self.debug_panel)
        layout.addWidget(left_frame, stretch=5)

        # RIGHT COLUMN: Action Editor Card
        right_frame = QFrame()
        right_frame.setObjectName("Card")
        rf_layout = QVBoxLayout(right_frame)
        rf_layout.setContentsMargins(18, 18, 18, 18)
        rf_layout.setSpacing(12)

        lbl_edit = QLabel("Action Editor")
        lbl_edit.setObjectName("HeaderLabel")
        rf_layout.addWidget(lbl_edit)

        lbl_edit_sub = QLabel("Configure parameters and append steps to the playlist")
        lbl_edit_sub.setObjectName("PageSubtitle")
        rf_layout.addWidget(lbl_edit_sub)

        action_layout = QVBoxLayout()
        action_layout.setSpacing(4)
        action_layout.addWidget(QLabel("Action Type", objectName="SectionLabel"))
        self.combo_wf_action = QComboBox()
        self.combo_wf_action.addItems([
            "Delay", "Click", "Key Press", "Type Text", "Wait Image", "Click Image", "AI Action"
        ])
        self.combo_wf_action.currentTextChanged.connect(self.on_action_combo_changed)
        action_layout.addWidget(self.combo_wf_action)
        rf_layout.addLayout(action_layout)

        self.wf_opts_container = QFrame()
        self.wf_opts_container.setObjectName("SubCard")
        self.wf_opts_layout = QVBoxLayout(self.wf_opts_container)
        self.wf_opts_layout.setContentsMargins(12, 12, 12, 12)
        self.wf_opts_layout.setSpacing(10)
        rf_layout.addWidget(self.wf_opts_container)

        self.wf_inputs = {}
        self.build_action_ui("Delay")

        rf_layout.addStretch()

        self.btn_wf_add = QPushButton("＋  ADD STEP")
        self.btn_wf_add.setObjectName("SuccessButton")
        self.btn_wf_add.setCursor(Qt.PointingHandCursor)
        self.btn_wf_add.setMinimumHeight(42)
        self.btn_wf_add.clicked.connect(self.save_wf_step)
        rf_layout.addWidget(self.btn_wf_add)

        self.btn_wf_cancel = QPushButton("Cancel Edit")
        self.btn_wf_cancel.setObjectName("DangerButton")
        self.btn_wf_cancel.setCursor(Qt.PointingHandCursor)
        self.btn_wf_cancel.setVisible(False)
        self.btn_wf_cancel.clicked.connect(self.cancel_wf_edit)
        rf_layout.addWidget(self.btn_wf_cancel)

        # --- API KEY FIELD ---
        api_card = QFrame()
        api_card.setObjectName("SubCard")
        api_layout = QVBoxLayout(api_card)
        api_layout.setContentsMargins(12, 10, 12, 10)
        api_layout.setSpacing(6)

        api_layout.addWidget(QLabel("🤖 Gemini API Key (For AI Actions)", objectName="SectionLabel"))
        self.le_api = QLineEdit()
        self.le_api.setEchoMode(QLineEdit.Password)
        self.le_api.setPlaceholderText("Paste your Gemini API Key...")

        if os.path.exists(self._settings_path):
            try:
                with open(self._settings_path, 'r') as f:
                    self.le_api.setText(json.load(f).get('gemini_key', ''))
            except Exception:
                pass

        self.le_api.textChanged.connect(lambda _: self._save_key_timer.start())
        api_layout.addWidget(self.le_api)
        rf_layout.addWidget(api_card)

        layout.addWidget(right_frame, stretch=5)

    def _do_save_key(self):
        """Write the API key to settings.json (called by debounce timer)."""
        data = {}
        if os.path.exists(self._settings_path):
            try:
                with open(self._settings_path, 'r') as f:
                    data = json.load(f)
            except Exception:
                pass
        data['gemini_key'] = self.le_api.text()
        with open(self._settings_path, 'w') as f:
            json.dump(data, f)

    # --- ACTION BUILDER ---
    def on_action_combo_changed(self, action_name):
        self.build_action_ui(action_name)
        if self.wf_selected_index != -1:
            self.commit_step_edit()

    def build_action_ui(self, action_name):
        self.clear_layout_recursive(self.wf_opts_layout)
        self.wf_inputs = {}

        def bind_change(widget):
            if isinstance(widget, (QSpinBox, QDoubleSpinBox)):
                widget.editingFinished.connect(self.commit_step_edit)
            elif isinstance(widget, QLineEdit):
                widget.returnPressed.connect(self.commit_step_edit)
            elif isinstance(widget, QComboBox):
                widget.activated.connect(self.commit_step_edit)
            elif isinstance(widget, QCheckBox):
                widget.stateChanged.connect(self.commit_step_edit)
            return widget

        if action_name == "Delay":
            self.wf_opts_layout.addWidget(QLabel("Duration (ms):", objectName="FieldLabel"))
            sb = bind_change(QSpinBox())
            sb.setRange(0, 3600000)
            sb.setValue(1000)
            sb.setSuffix(" ms")
            self.wf_opts_layout.addWidget(sb)
            self.wf_inputs['duration'] = sb

        elif action_name == "Click":
            h = QHBoxLayout()
            h.addWidget(QLabel("X:", objectName="FieldLabel"))
            x = bind_change(QSpinBox())
            x.setRange(0, 9999)
            h.addWidget(x)
            self.wf_inputs['x'] = x

            h.addWidget(QLabel("Y:", objectName="FieldLabel"))
            y = bind_change(QSpinBox())
            y.setRange(0, 9999)
            h.addWidget(y)
            self.wf_inputs['y'] = y
            self.wf_opts_layout.addLayout(h)

            h2 = QHBoxLayout()
            h2.addWidget(QLabel("Button:", objectName="FieldLabel"))
            b = bind_change(QComboBox())
            b.addItems(["left", "right", "middle"])
            h2.addWidget(b)
            self.wf_inputs['button'] = b

            h2.addWidget(QLabel("Type:", objectName="FieldLabel"))
            t = bind_change(QComboBox())
            t.addItems(["single", "double"])
            h2.addWidget(t)
            self.wf_inputs['type'] = t
            self.wf_opts_layout.addLayout(h2)

            btn_pick = QPushButton("🎯 Pick Screen Position (3s delay)")
            btn_pick.setCursor(Qt.PointingHandCursor)
            btn_pick.clicked.connect(self.pick_pos_trigger)
            self.wf_opts_layout.addWidget(btn_pick)

        elif action_name == "Key Press":
            self.wf_opts_layout.addWidget(QLabel("Key or Shortcut (e.g. enter, ctrl+c, win+r):", objectName="FieldLabel"))
            le = bind_change(QLineEdit())
            le.setPlaceholderText("e.g. ctrl+v")
            self.wf_opts_layout.addWidget(le)
            self.wf_inputs['key'] = le

        elif action_name == "Type Text":
            self.wf_opts_layout.addWidget(QLabel("Text to Type:", objectName="FieldLabel"))
            le = bind_change(QLineEdit())
            le.setPlaceholderText("Enter text string...")
            self.wf_opts_layout.addWidget(le)
            self.wf_inputs['text'] = le

        elif action_name in ["Wait Image", "Click Image"]:
            self.wf_opts_layout.addWidget(QLabel("Target Image (Snip, Paste, or Browse):", objectName="FieldLabel"))
            path_row = QHBoxLayout()
            le = bind_change(QLineEdit())
            le.setPlaceholderText("Snip, Paste image, or select file...")
            path_row.addWidget(le, stretch=1)
            self.wf_inputs['image_path'] = le

            btn_snip = QPushButton("✂️ Snip")
            btn_snip.setObjectName("SuccessButton")
            btn_snip.setCursor(Qt.PointingHandCursor)
            btn_snip.clicked.connect(lambda: self.snip_for_input(le))
            path_row.addWidget(btn_snip)

            btn_paste = QPushButton("📋 Paste")
            btn_paste.setCursor(Qt.PointingHandCursor)
            btn_paste.clicked.connect(lambda: self.paste_image_for_input(le))
            path_row.addWidget(btn_paste)

            btn_b = QPushButton("Browse")
            btn_b.setCursor(Qt.PointingHandCursor)
            btn_b.clicked.connect(lambda: self.browse_file_for_input(le))
            path_row.addWidget(btn_b)
            self.wf_opts_layout.addLayout(path_row)

            # Mini image preview
            preview_lbl = QLabel("No image selected")
            preview_lbl.setAlignment(Qt.AlignCenter)
            preview_lbl.setMinimumHeight(54)
            preview_lbl.setMaximumHeight(64)
            preview_lbl.setObjectName("FieldLabel")
            self.wf_opts_layout.addWidget(preview_lbl)

            def _refresh_preview(p, lbl=preview_lbl):
                p = p.strip()
                if p and os.path.isfile(p):
                    pix = QPixmap(p)
                    if not pix.isNull():
                        lbl.setPixmap(pix.scaled(180, 52, Qt.KeepAspectRatio, Qt.SmoothTransformation))
                        return
                lbl.setPixmap(QPixmap())
                lbl.setText("No image selected")

            le.textChanged.connect(_refresh_preview)

            # Target Monitor dropdown
            mon_row = QHBoxLayout()
            mon_row.addWidget(QLabel("Target Monitor:", objectName="FieldLabel"))
            mon_combo = bind_change(QComboBox())
            for mon in get_monitors():
                mon_combo.addItem(mon["name"], mon["rect"])
            mon_row.addWidget(mon_combo, stretch=1)
            self.wf_opts_layout.addLayout(mon_row)
            self.wf_inputs['monitor_name'] = mon_combo

            params_row = QHBoxLayout()
            params_row.addWidget(QLabel("Timeout (s):", objectName="FieldLabel"))
            sb = bind_change(QDoubleSpinBox())
            sb.setRange(0.5, 300.0)
            sb.setValue(10.0)
            params_row.addWidget(sb)
            self.wf_inputs['timeout'] = sb

            params_row.addWidget(QLabel("Confidence:", objectName="FieldLabel"))
            sb2 = bind_change(QDoubleSpinBox())
            sb2.setRange(0.1, 1.0)
            sb2.setValue(0.8)
            sb2.setSingleStep(0.05)
            params_row.addWidget(sb2)
            self.wf_inputs['confidence'] = sb2
            self.wf_opts_layout.addLayout(params_row)

            if action_name == "Click Image":
                chk_ret = bind_change(QCheckBox("Return mouse to original position after click"))
                chk_ret.setChecked(True)
                self.wf_opts_layout.addWidget(chk_ret)
                self.wf_inputs['return_cursor'] = chk_ret

        elif action_name == "AI Action":
            self.wf_opts_layout.addWidget(QLabel("Autonomous Goal Prompt:", objectName="FieldLabel"))
            le = bind_change(QLineEdit())
            le.setPlaceholderText("e.g. 'Open Notepad and write Hello'")
            self.wf_opts_layout.addWidget(le)
            self.wf_inputs['prompt'] = le

    def clear_layout_recursive(self, layout):
        if layout is None:
            return
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
            elif item.layout():
                self.clear_layout_recursive(item.layout())

    def pick_pos_trigger(self):
        QMessageBox.information(self, "Pick Position", "Capturing cursor position in 3 seconds. Hover over your target!")
        QTimer.singleShot(3000, self.capture_pos_delayed)

    def capture_pos_delayed(self):
        import pyautogui
        x, y = pyautogui.position()
        if 'x' in self.wf_inputs:
            self.wf_inputs['x'].setValue(int(x))
            self.wf_inputs['y'].setValue(int(y))
            self.commit_step_edit()
        QMessageBox.information(self, "Captured", f"Captured Coordinates: X={x}, Y={y}")

    def browse_file_for_input(self, line_edit):
        f, _ = QFileDialog.getOpenFileName(self, "Select Image", "", "Images (*.png *.jpg *.jpeg)")
        if f:
            line_edit.setText(f)
            self.commit_step_edit()

    def paste_image_for_input(self, line_edit):
        clipboard = QApplication.clipboard()
        image = clipboard.image()
        if image is None or image.isNull():
            QMessageBox.information(self, "Paste Image", "Clipboard does not contain an image. Take a snip first!")
            return
        saved = save_qimage_snip(image, prefix="wf_pasted")
        if saved:
            line_edit.setText(saved)
            self.commit_step_edit()

    def snip_for_input(self, line_edit):
        top_win = self.window()
        if top_win and top_win.isVisible():
            top_win.hide()

        def _launch():
            self._snip_overlay = SnipOverlay()

            def _restore():
                if top_win:
                    top_win.show()
                    top_win.raise_()
                    top_win.activateWindow()

            def _on_captured(pixmap: QPixmap):
                _restore()
                saved = save_qimage_snip(pixmap, prefix="wf_snip")
                if saved:
                    line_edit.setText(saved)
                    self.commit_step_edit()

            self._snip_overlay.snip_captured.connect(_on_captured)
            self._snip_overlay.snip_cancelled.connect(_restore)
            self._snip_overlay.start_snip()

        QTimer.singleShot(180, _launch)

    # --- LIST MANAGEMENT ---
    def _collect_params(self):
        params = {}
        for k, w in self.wf_inputs.items():
            if isinstance(w, (QSpinBox, QDoubleSpinBox)):
                params[k] = w.value()
            elif isinstance(w, QLineEdit):
                params[k] = w.text()
            elif isinstance(w, QCheckBox):
                params[k] = w.isChecked()
            elif isinstance(w, QComboBox):
                params[k] = w.currentText()
                if k == 'monitor_name':
                    rect = w.currentData()
                    params['monitor_rect'] = list(rect) if rect is not None else None
        return params

    def commit_step_edit(self):
        if self.wf_selected_index == -1:
            return

        action = self.combo_wf_action.currentText()
        params = self._collect_params()
        step = {'action': action, 'params': params}

        if 0 <= self.wf_selected_index < len(self.workflow_steps):
            self.workflow_steps[self.wf_selected_index] = step
            item = self.wf_list.item(self.wf_selected_index)
            item.setText(self.format_step_text(step))
            item.setData(Qt.UserRole, step)

    def format_step_text(self, step):
        txt = f"{step['action']}"
        p = step.get('params', {})
        if step['action'] == "Delay":
            txt += f" ({p.get('duration', 1000)}ms)"
        elif step['action'] == "Click":
            txt += f" {p.get('button', 'left')} ({p.get('x', 0)},{p.get('y', 0)})"
        elif "Image" in step['action']:
            txt += f" {os.path.basename(str(p.get('image_path', '')))}"
            mon = p.get('monitor_name', '')
            if mon:
                short_mon = mon.split(":")[0] if ":" in mon else mon.split(" (")[0]
                txt += f" [{short_mon}]"
        elif step['action'] == "Type Text":
            txt += f" '{p.get('text', '')}'"
        elif step['action'] == "Key Press":
            txt += f" [{p.get('key', '')}]"
        elif step['action'] == "AI Action":
            txt += f" '{p.get('prompt', '')}'"
        return txt

    def save_wf_step(self):
        action = self.combo_wf_action.currentText()
        params = self._collect_params()
        step = {'action': action, 'params': params}

        self.cancel_wf_edit()
        self.workflow_steps.append(step)
        self.refresh_wf_list()
        self.wf_list.scrollToBottom()

    def refresh_wf_list(self):
        curr = self.wf_list.currentRow()
        self.wf_list.setUpdatesEnabled(False)
        self.wf_list.clear()
        for step in self.workflow_steps:
            item = QListWidgetItem(self.format_step_text(step))
            item.setData(Qt.UserRole, step)
            self.wf_list.addItem(item)

        if 0 <= curr < self.wf_list.count():
            self.wf_list.setCurrentRow(curr)
        self.wf_list.setUpdatesEnabled(True)
        count = len(self.workflow_steps)
        self.lbl_step_count.setText(f"{count} step{'s' if count != 1 else ''}")

    def sync_wf_order(self):
        new_steps = []
        for i in range(self.wf_list.count()):
            step_data = self.wf_list.item(i).data(Qt.UserRole)
            if step_data:
                new_steps.append(step_data)
        self.workflow_steps = new_steps
        count = len(self.workflow_steps)
        self.lbl_step_count.setText(f"{count} step{'s' if count != 1 else ''}")

    def copy_wf_step(self):
        row = self.wf_list.currentRow()
        if row >= 0:
            step = self.workflow_steps[row]
            QApplication.clipboard().setText(json.dumps(step))

    def paste_wf_step(self):
        text = QApplication.clipboard().text()
        try:
            step = json.loads(text)
            if 'action' in step and 'params' in step:
                row = self.wf_list.currentRow()
                target = len(self.workflow_steps) if row < 0 else row + 1
                self.workflow_steps.insert(target, step)
                self.refresh_wf_list()
                self.wf_list.setCurrentRow(target)
        except Exception:
            pass

    def on_wf_item_select(self, item):
        idx = self.wf_list.row(item)
        self.wf_selected_index = idx
        step = self.workflow_steps[idx]

        self.combo_wf_action.blockSignals(True)
        self.combo_wf_action.setCurrentText(step['action'])
        self.combo_wf_action.blockSignals(False)

        self.build_action_ui(step['action'])

        for k, val in step.get('params', {}).items():
            if k in self.wf_inputs:
                w = self.wf_inputs[k]
                w.blockSignals(True)
                if isinstance(w, (QSpinBox, QDoubleSpinBox)):
                    w.setValue(float(val))
                elif isinstance(w, QLineEdit):
                    w.setText(str(val))
                elif isinstance(w, QCheckBox):
                    w.setChecked(bool(val))
                elif isinstance(w, QComboBox):
                    w.setCurrentText(str(val))
                w.blockSignals(False)

        self.btn_wf_add.setText("✓  SAVE MODIFIED STEP")
        self.btn_wf_add.setObjectName("SuccessButton")
        self.btn_wf_cancel.setVisible(True)

    def cancel_wf_edit(self):
        self.wf_selected_index = -1
        self.wf_list.clearSelection()
        self.btn_wf_add.setText("＋  ADD STEP")
        self.btn_wf_cancel.setVisible(False)

    def del_wf_item(self):
        row = self.wf_list.currentRow()
        if row >= 0:
            del self.workflow_steps[row]
            self.refresh_wf_list()
            self.cancel_wf_edit()

    def move_wf_item(self, direction):
        row = self.wf_list.currentRow()
        if row < 0:
            return
        new_row = row + direction
        if 0 <= new_row < len(self.workflow_steps):
            self.workflow_steps[row], self.workflow_steps[new_row] = (
                self.workflow_steps[new_row],
                self.workflow_steps[row],
            )
            self.refresh_wf_list()
            self.wf_list.setCurrentRow(new_row)

    def save_workflow(self):
        f, _ = QFileDialog.getSaveFileName(self, "Save Workflow", "", "JSON (*.json)")
        if f:
            with open(f, 'w') as file:
                json.dump(self.workflow_steps, file, indent=2)

    def load_workflow(self):
        f, _ = QFileDialog.getOpenFileName(self, "Load Workflow", "", "JSON (*.json)")
        if f:
            with open(f, 'r') as file:
                self.workflow_steps = json.load(file)
                self.refresh_wf_list()

    # --- EXECUTION ---
    @Slot()
    def toggle_clicking(self):
        if self.is_running:
            self.stop_workflow()
        else:
            self.start_workflow()

    def start_workflow(self):
        if self.is_running or not self.workflow_steps:
            return

        self.runner.api_key = self.le_api.text().strip()

        self.stop_event.clear()
        self.txt_debug.clear()

        self.worker_thread = WorkflowThread(self.runner, self.workflow_steps)
        self.worker_thread.step_highlight.connect(self.highlight_exec_step)
        self.worker_thread.ai_debug.connect(self.append_debug_log)
        self.worker_thread.finished.connect(self.on_thread_finished)
        self.worker_thread.start()

        self.status_changed.emit(True)

    def stop_workflow(self):
        if not self.is_running:
            return
        self.stop_event.set()
        self.status_changed.emit(False)
        self.clear_execution_highlights()

    def on_thread_finished(self):
        self.status_changed.emit(False)
        self.clear_execution_highlights()

    def highlight_exec_step(self, index):
        self.clear_execution_highlights()
        if 0 <= index < self.wf_list.count():
            item = self.wf_list.item(index)
            item.setBackground(QColor("#1D4ED8"))

    def clear_execution_highlights(self):
        for i in range(self.wf_list.count()):
            self.wf_list.item(i).setBackground(Qt.GlobalColor.transparent)

    @Slot(str)
    def append_debug_log(self, msg):
        self.debug_panel.setVisible(True)
        self.txt_debug.append(f"> {msg}")
        self.txt_debug.verticalScrollBar().setValue(self.txt_debug.verticalScrollBar().maximum())

    def update_ui_state(self, is_running):
        self.is_running = is_running
        if is_running:
            self.btn_start_wf.setText("STOP WORKFLOW (F6)")
            self.btn_start_wf.setObjectName("DangerButton")
            self.btn_wf_add.setEnabled(False)
        else:
            self.btn_start_wf.setText("RUN WORKFLOW (F6)")
            self.btn_start_wf.setObjectName("PrimaryButton")
            self.btn_wf_add.setEnabled(True)

        self.btn_start_wf.style().unpolish(self.btn_start_wf)
        self.btn_start_wf.style().polish(self.btn_start_wf)
