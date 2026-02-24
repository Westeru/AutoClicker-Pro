import json
import os
import threading
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, 
    QPushButton, QDoubleSpinBox, QFileDialog,
    QListWidget, QAbstractItemView, QMenu, QSpinBox, QComboBox,
    QFrame, QMessageBox, QListWidgetItem, QApplication, QTextEdit
)
from PySide6.QtGui import QKeySequence, QAction, QShortcut
from PySide6.QtCore import Qt, Signal, QThread, QTimer, Slot
from src.workflow_runner import WorkflowRunner

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
            # We defer to the parent window handling shortcuts via QShortcut
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

        self.setup_ui()
        self.status_changed.connect(self.update_ui_state)

    def setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(20)

        # LEFT COLUMN: List & Tools
        left_frame = QWidget()
        lf_layout = QVBoxLayout(left_frame)
        lf_layout.setContentsMargins(0,0,0,0)
        
        lbl_list = QLabel("Workflow Playlist")
        lbl_list.setObjectName("HeaderLabel")
        lf_layout.addWidget(lbl_list)

        self.wf_list = ReorderableListWidget()
        self.wf_list.order_changed.connect(self.sync_wf_order)
        self.wf_list.delete_key_pressed.connect(self.del_wf_item)
        self.wf_list.itemDoubleClicked.connect(self.on_wf_item_select) 
        self.wf_list.setStyleSheet("""
            QListWidget::item { padding: 8px; border-bottom: 1px solid #333; }
            QListWidget::item:selected { background-color: #BB86FC; color: #000; font-weight: bold; }
        """)
        lf_layout.addWidget(self.wf_list)
        
        # Shortcuts for Copy/Paste
        QShortcut(QKeySequence.Copy, self.wf_list, self.copy_wf_step)
        QShortcut(QKeySequence.Paste, self.wf_list, self.paste_wf_step)
        
        # Tools
        tools_layout = QHBoxLayout()
        btn_up = QPushButton("Up"); btn_up.clicked.connect(lambda: self.move_wf_item(-1))
        btn_down = QPushButton("Down"); btn_down.clicked.connect(lambda: self.move_wf_item(1))
        btn_del = QPushButton("Delete"); btn_del.setObjectName("DangerButton"); btn_del.clicked.connect(self.del_wf_item)
        tools_layout.addWidget(btn_up); tools_layout.addWidget(btn_down); tools_layout.addWidget(btn_del)
        lf_layout.addLayout(tools_layout)
        
        # Save/Load Flow
        sl_layout = QHBoxLayout()
        btn_s = QPushButton("Save Flow"); btn_s.clicked.connect(self.save_workflow)
        btn_l = QPushButton("Load Flow"); btn_l.clicked.connect(self.load_workflow)
        sl_layout.addWidget(btn_s); sl_layout.addWidget(btn_l)
        lf_layout.addLayout(sl_layout)

        # Action Buttons
        run_layout = QHBoxLayout()
        self.btn_start_wf = QPushButton("RUN WORKFLOW (F6)")
        self.btn_start_wf.setObjectName("PrimaryButton")
        self.btn_start_wf.setMinimumHeight(45)
        self.btn_start_wf.clicked.connect(self.toggle_clicking)
        run_layout.addWidget(self.btn_start_wf)
        
        lf_layout.addLayout(run_layout)
        
        # Debug Panel (Hidden by default)
        self.debug_panel = QFrame()
        self.debug_panel.setVisible(False)
        dp_layout = QVBoxLayout(self.debug_panel)
        dp_layout.setContentsMargins(0, 10, 0, 0)
        
        lbl_debug = QLabel("AI Debug Log")
        lbl_debug.setObjectName("SectionLabel")
        dp_layout.addWidget(lbl_debug)
        
        self.txt_debug = QTextEdit()
        self.txt_debug.setReadOnly(True)
        self.txt_debug.setMaximumHeight(100)
        dp_layout.addWidget(self.txt_debug)
        
        lf_layout.addWidget(self.debug_panel)

        layout.addWidget(left_frame, 1) # Left takes half space

        # RIGHT COLUMN: Editor
        right_frame = QFrame()
        right_frame.setObjectName("SidebarFrame") 
        right_frame.setStyleSheet("background-color: #1A1A1A; border-radius: 8px; padding: 10px;")
        rf_layout = QVBoxLayout(right_frame)
        
        lbl_edit = QLabel("Action Editor")
        lbl_edit.setObjectName("HeaderLabel")
        rf_layout.addWidget(lbl_edit)
        
        action_layout = QHBoxLayout()
        action_layout.addWidget(QLabel("Action Type:"))
        self.combo_wf_action = QComboBox()
        self.combo_wf_action.addItems(["Delay", "Click", "Key Press", "Type Text", "Wait Image", "Click Image", "AI Action"])
        self.combo_wf_action.currentTextChanged.connect(self.on_action_combo_changed)
        action_layout.addWidget(self.combo_wf_action)
        rf_layout.addLayout(action_layout)
        
        self.wf_opts_container = QWidget()
        self.wf_opts_layout = QVBoxLayout(self.wf_opts_container)
        self.wf_opts_layout.setContentsMargins(0, 10, 0, 0)
        rf_layout.addWidget(self.wf_opts_container)
        
        self.wf_inputs = {}
        self.build_action_ui("Delay") 
        
        rf_layout.addStretch()
        
        self.btn_wf_add = QPushButton("ADD STEP")
        self.btn_wf_add.setObjectName("SuccessButton")
        self.btn_wf_add.setMinimumHeight(40)
        self.btn_wf_add.clicked.connect(self.save_wf_step)
        rf_layout.addWidget(self.btn_wf_add)
        
        self.btn_wf_cancel = QPushButton("Cancel Edit")
        self.btn_wf_cancel.setObjectName("DangerButton")
        self.btn_wf_cancel.setVisible(False)
        self.btn_wf_cancel.clicked.connect(self.cancel_wf_edit)
        rf_layout.addWidget(self.btn_wf_cancel)
        
        # --- API KEY FIELD ---
        rf_layout.addStretch()
        rf_layout.addWidget(QLabel("Gemini API Key (Required for AI actions):"))
        self.le_api = QLineEdit()
        self.le_api.setEchoMode(QLineEdit.Password)
        self.le_api.setPlaceholderText("Enter API Key...")
        
        if os.path.exists('settings.json'):
            try:
                with open('settings.json', 'r') as f:
                    self.le_api.setText(json.load(f).get('gemini_key', ''))
            except: pass
            
        def save_key(t):
            data = {}
            if os.path.exists('settings.json'):
                try: 
                    with open('settings.json', 'r') as f: data = json.load(f)
                except: pass
            data['gemini_key'] = t
            with open('settings.json', 'w') as f: json.dump(data, f)
            
        self.le_api.textChanged.connect(save_key)
        rf_layout.addWidget(self.le_api)
        
        layout.addWidget(right_frame, 1)

    # --- ACTION BUILDER ---
    def on_action_combo_changed(self, action_name):
        self.build_action_ui(action_name)
        if self.wf_selected_index != -1:
            self.commit_step_edit()

    def build_action_ui(self, action_name):
        self.clear_layout_recursive(self.wf_opts_layout)
        self.wf_inputs = {}
        
        def bind_change(widget):
            if isinstance(widget, (QSpinBox, QDoubleSpinBox)): widget.editingFinished.connect(self.commit_step_edit)
            elif isinstance(widget, QLineEdit): widget.returnPressed.connect(self.commit_step_edit)
            elif isinstance(widget, QComboBox): widget.activated.connect(self.commit_step_edit)
            return widget
        
        if action_name == "Delay":
            self.wf_opts_layout.addWidget(QLabel("Duration (ms):"))
            sb = bind_change(QSpinBox()); sb.setRange(0, 3600000); sb.setValue(1000)
            self.wf_opts_layout.addWidget(sb); self.wf_inputs['duration'] = sb
            
        elif action_name == "Click":
            h = QHBoxLayout()
            h.addWidget(QLabel("X:")); x = bind_change(QSpinBox()); x.setRange(0, 9999); h.addWidget(x); self.wf_inputs['x'] = x
            h.addWidget(QLabel("Y:")); y = bind_change(QSpinBox()); y.setRange(0, 9999); h.addWidget(y); self.wf_inputs['y'] = y
            self.wf_opts_layout.addLayout(h)
            
            h2 = QHBoxLayout()
            h2.addWidget(QLabel("Btn:")); b = bind_change(QComboBox()); b.addItems(["left", "right", "middle"]); h2.addWidget(b); self.wf_inputs['button'] = b
            h2.addWidget(QLabel("Type:")); t = bind_change(QComboBox()); t.addItems(["single", "double"]); h2.addWidget(t); self.wf_inputs['type'] = t
            self.wf_opts_layout.addLayout(h2)

            btn_pick = QPushButton("Pick Position (F8)")
            btn_pick.clicked.connect(self.pick_pos_trigger)
            self.wf_opts_layout.addWidget(btn_pick)
            
        elif action_name == "Key Press":
            self.wf_opts_layout.addWidget(QLabel("Key (e.g. enter, ctrl+c):"))
            le = bind_change(QLineEdit()); self.wf_opts_layout.addWidget(le); self.wf_inputs['key'] = le
            
        elif action_name == "Type Text":
            self.wf_opts_layout.addWidget(QLabel("Text:"))
            le = bind_change(QLineEdit()); self.wf_opts_layout.addWidget(le); self.wf_inputs['text'] = le
            
        elif action_name in ["Wait Image", "Click Image"]:
            self.wf_opts_layout.addWidget(QLabel("Image Path:"))
            le = bind_change(QLineEdit()); self.wf_opts_layout.addWidget(le); self.wf_inputs['image_path'] = le
            
            btn_b = QPushButton("Browse"); btn_b.clicked.connect(lambda: self.browse_file_for_input(le))
            self.wf_opts_layout.addWidget(btn_b)
            
            self.wf_opts_layout.addWidget(QLabel("Timeout (s):"))
            sb = bind_change(QDoubleSpinBox()); sb.setValue(10.0); self.wf_opts_layout.addWidget(sb); self.wf_inputs['timeout'] = sb
            
            
            self.wf_opts_layout.addWidget(QLabel("Confidence:"))
            sb2 = bind_change(QDoubleSpinBox()); sb2.setValue(0.8); sb2.setSingleStep(0.05); self.wf_opts_layout.addWidget(sb2); self.wf_inputs['confidence'] = sb2
            
        elif action_name == "AI Action":
            self.wf_opts_layout.addWidget(QLabel("Prompt (e.g. 'Open Notepad'):"))
            le = bind_change(QLineEdit()); self.wf_opts_layout.addWidget(le); self.wf_inputs['prompt'] = le

    def clear_layout_recursive(self, layout):
        if layout is None: return
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget: widget.deleteLater()
            elif item.layout(): self.clear_layout_recursive(item.layout())

    def pick_pos_trigger(self):
        QMessageBox.information(self, "Pick Position", "Capturing position in 3 seconds. Hover over target!")
        QTimer.singleShot(3000, self.capture_pos_delayed)

    def capture_pos_delayed(self):
        import pyautogui
        x, y = pyautogui.position()
        if 'x' in self.wf_inputs:
            self.wf_inputs['x'].setValue(int(x))
            self.wf_inputs['y'].setValue(int(y))
            self.commit_step_edit() # Auto save since we captured
        QMessageBox.information(self, "Captured", f"Captured: {x}, {y}")

    def browse_file_for_input(self, line_edit):
        f, _ = QFileDialog.getOpenFileName(self, "Select Image", "", "Images (*.png *.jpg *.jpeg)")
        if f: 
            line_edit.setText(f)
            self.commit_step_edit()

    # --- LIST MANAGEMENT ---
    def commit_step_edit(self):
        if self.wf_selected_index == -1: return
        
        action = self.combo_wf_action.currentText()
        params = {}
        for k, w in self.wf_inputs.items():
            if isinstance(w, (QSpinBox, QDoubleSpinBox)): params[k] = w.value()
            elif isinstance(w, QLineEdit): params[k] = w.text()
            elif isinstance(w, QComboBox): params[k] = w.currentText()
        
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
        elif step['action'] == "Type Text": 
            txt += f" '{p.get('text', '')}'"
        elif step['action'] == "Key Press": 
            txt += f" [{p.get('key', '')}]"
        elif step['action'] == "AI Action":
            txt += f" '{p.get('prompt', '')}'"
        return txt

    def save_wf_step(self):
        action = self.combo_wf_action.currentText()
        params = {}
        for k, w in self.wf_inputs.items():
            if isinstance(w, (QSpinBox, QDoubleSpinBox)): params[k] = w.value()
            elif isinstance(w, QLineEdit): params[k] = w.text()
            elif isinstance(w, QComboBox): params[k] = w.currentText()
        
        step = {'action': action, 'params': params}
        
        self.cancel_wf_edit() # Add as new
        self.workflow_steps.append(step)
        self.refresh_wf_list()
        self.wf_list.scrollToBottom()

    def refresh_wf_list(self):
        curr = self.wf_list.currentRow()
        self.wf_list.clear()
        for i, step in enumerate(self.workflow_steps):
            item = QListWidgetItem(self.format_step_text(step))
            item.setData(Qt.UserRole, step) 
            self.wf_list.addItem(item)
            
        if 0 <= curr < self.wf_list.count():
             self.wf_list.setCurrentRow(curr)

    def sync_wf_order(self):
        new_steps = []
        for i in range(self.wf_list.count()):
            step_data = self.wf_list.item(i).data(Qt.UserRole)
            if step_data: new_steps.append(step_data)
        self.workflow_steps = new_steps
        
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
                if isinstance(w, (QSpinBox, QDoubleSpinBox)): w.setValue(float(val))
                elif isinstance(w, QLineEdit): w.setText(str(val))
                elif isinstance(w, QComboBox): w.setCurrentText(str(val))
                w.blockSignals(False)
        
        self.btn_wf_add.setText("SAVE MODIFIED STEP") 
        self.btn_wf_add.setObjectName("SuccessButton") 
        self.btn_wf_cancel.setVisible(True) 

    def cancel_wf_edit(self):
        self.wf_selected_index = -1
        self.wf_list.clearSelection()
        self.btn_wf_add.setText("ADD STEP")
        self.btn_wf_cancel.setVisible(False)
        
    def del_wf_item(self):
        row = self.wf_list.currentRow()
        if row >= 0:
            del self.workflow_steps[row]
            self.refresh_wf_list()
            self.cancel_wf_edit()

    def move_wf_item(self, direction):
        row = self.wf_list.currentRow()
        if row < 0: return
        new_row = row + direction
        if 0 <= new_row < len(self.workflow_steps):
            self.workflow_steps[row], self.workflow_steps[new_row] = self.workflow_steps[new_row], self.workflow_steps[row]
            self.refresh_wf_list()
            self.wf_list.setCurrentRow(new_row)

    def save_workflow(self):
        f, _ = QFileDialog.getSaveFileName(self, "Save Workflow", "", "JSON (*.json)")
        if f:
            with open(f, 'w') as file: json.dump(self.workflow_steps, file, indent=2)

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
        if self.is_running or not self.workflow_steps: return
        
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
        if not self.is_running: return
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
            # Give it a bold blue background to indicate it is running
            item.setBackground(Qt.GlobalColor.darkBlue)

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
