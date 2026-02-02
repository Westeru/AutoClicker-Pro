import customtkinter as ctk
import pyautogui
import threading
import time
import json
import math
from tkinter import filedialog, messagebox
from pynput import keyboard as pynput_keyboard
from pynput import mouse as pynput_mouse
from pynput.mouse import Button, Controller as MouseController
from pynput.keyboard import Key, Controller as KeyboardController

# Configuration
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

# --- RECORDER LOGIC ---
class Recorder:
    def __init__(self):
        self.events = []
        self.recording = False
        self.start_time = 0
        self.mouse_listener = None
        self.key_listener = None
        # Keys to ignore (Control keys)
        self.ignore_keys = [] 
        
    def start(self):
        self.events = []
        self.recording = True
        self.start_time = time.time()
        
        # Define keys to ignore dynamically
        # We ignore F6 (Safety) and F7 (Record Toggle)
        self.ignore_keys = [Key.f6, Key.f7]

        self.mouse_listener = pynput_mouse.Listener(
            on_move=self.on_move,
            on_click=self.on_click,
            on_scroll=self.on_scroll
        )
        self.key_listener = pynput_keyboard.Listener(
            on_press=self.on_press,
            on_release=self.on_release
        )
        
        self.mouse_listener.start()
        self.key_listener.start()

    def stop(self, remove_last_click=False):
        self.recording = False
        if self.mouse_listener: self.mouse_listener.stop()
        if self.key_listener: self.key_listener.stop()
        
        if remove_last_click and self.events:
            # Remove the last click sequence (press and release)
            # Iterate backwards
            new_events = []
            click_removed = False
            
            # We want to remove the very last 'click' block (usually press then release)
            # But events are appended chronologically.
            
            # Simple heuristic: Remove all events that happened in the last 0.2 seconds?
            # Or explicitly find the last click.
            
            # Let's filter out the last 'click' events if they are at the end.
            # A click usually consists of 'move' (optional), 'click' (pressed=True), 'click' (pressed=False)
            
            # Better approach: Just pop from the end until we hit a click release/press pair?
            # User request: "delete the last click action"
            
            # Let's delete the last 2 'click' type events (press and release)
            click_evs = [i for i, x in enumerate(self.events) if x['type'] == 'click']
            if len(click_evs) >= 2:
                # Assuming the last two are the stop click
                 last_idx = click_evs[-1]
                 second_last = click_evs[-2]
                 
                 # Only remove if they are at the very end (ignoring maybe a tiny move)
                 if last_idx > len(self.events) - 5:
                     # Remove everything after the start of that click
                     self.events = self.events[:second_last]

    def _add_event(self, type, **kwargs):
        if not self.recording: return
        event = {
            "type": type,
            "time": time.time() - self.start_time,
            **kwargs
        }
        self.events.append(event)

    def on_move(self, x, y):
        self._add_event("move", x=x, y=y)

    def on_click(self, x, y, button, pressed):
        btn_str = str(button).replace('Button.', '')
        self._add_event("click", x=x, y=y, button=btn_str, pressed=pressed)

    def on_scroll(self, x, y, dx, dy):
        self._add_event("scroll", x=x, y=y, dx=dx, dy=dy)
        
    def on_press(self, key):
        if key in self.ignore_keys: return
        try: k = key.char
        except: k = str(key)
        self._add_event("key_press", key=k)

    def on_release(self, key):
        if key in self.ignore_keys: return
        try: k = key.char
        except: k = str(key)
        self._add_event("key_release", key=k)

# --- MAIN APP ---
class AutoclickerApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        # --- Window Setup ---
        self.title("Autoclicker Pro (Python)")
        self.geometry("500x650")
        self.resizable(True, True)

        # --- State ---
        self.running = False
        self.stop_event = threading.Event()
        self.click_thread = None
        
        self.mouse = MouseController()
        self.keyboard = KeyboardController()
        self.recorder = Recorder()
        
        # --- UI ---
        self.create_header()
        
        # TABS
        self.tab_view = ctk.CTkTabview(self, width=460, height=500)
        self.tab_view.pack(pady=10, padx=20, fill="both", expand=True)
        
        self.tab_clicker = self.tab_view.add("Autoclicker")
        self.tab_recorder = self.tab_view.add("Recorder")
        self.tab_img = self.tab_view.add("Image Search")
        
        self.setup_clicker_tab()
        self.setup_recorder_tab()
        self.setup_image_tab()
        
        # Global Hotkey
        self.listener = pynput_keyboard.GlobalHotKeys({
            '<f6>': self.toggle_via_hotkey,
            '<f7>': self.toggle_rec_hotkey
        })
        self.listener.start()

    def create_header(self):
        info_frame = ctk.CTkFrame(self, fg_color="transparent")
        info_frame.pack(pady=(20, 5))
        ctk.CTkLabel(info_frame, text="AUTOCLICKER PRO", font=("Inter", 24, "bold")).pack()
        self.status_label = ctk.CTkLabel(info_frame, text="STOPPED", text_color="gray", font=("Inter", 12, "bold"))
        self.status_label.pack()

    # --- CLICKER TAB ---
    def setup_clicker_tab(self):
        tab = self.tab_clicker
        
        # Interval
        ctk.CTkLabel(tab, text="Interval").pack(pady=5)
        int_frame = ctk.CTkFrame(tab, fg_color="transparent")
        int_frame.pack()
        self.inputs = {}
        for i, u in enumerate(['Hours', 'Mins', 'Secs', 'MS']):
            f = ctk.CTkFrame(int_frame, fg_color="transparent")
            f.grid(row=0, column=i, padx=5)
            ctk.CTkLabel(f, text=u, font=("Arial", 10)).pack()
            e = ctk.CTkEntry(f, width=50, justify="center")
            e.insert(0, "0" if u != "MS" else "100")
            e.pack()
            self.inputs[u.lower()] = e

        # Mouse Options
        ctk.CTkLabel(tab, text="Action Type").pack(pady=(10, 5))
        
        # Action Switcher
        self.action_type = ctk.StringVar(value="mouse")
        
        # Mouse Frame
        self.mouse_frame = ctk.CTkFrame(tab, fg_color="transparent")
        self.mouse_frame.pack(pady=5)
        
        ctk.CTkLabel(self.mouse_frame, text="Mouse Button").pack()
        self.click_btn_var = ctk.StringVar(value="left")
        ctk.CTkSegmentedButton(self.mouse_frame, values=["left", "middle", "right"], variable=self.click_btn_var).pack(pady=2)
        
        ctk.CTkLabel(self.mouse_frame, text="Click Type").pack()
        self.click_type_var = ctk.StringVar(value="single")
        ctk.CTkSegmentedButton(self.mouse_frame, values=["single", "double"], variable=self.click_type_var).pack(pady=2)

        # Key Frame
        self.key_frame = ctk.CTkFrame(tab, fg_color="transparent")
        # Don't pack initially

        ctk.CTkLabel(self.key_frame, text="Key (e.g. space, enter, f)").pack()
        self.key_entry = ctk.CTkEntry(self.key_frame, placeholder_text="space")
        self.key_entry.pack(pady=2)
        
        self.key_mode_var = ctk.StringVar(value="press")
        ctk.CTkSegmentedButton(self.key_frame, values=["press", "hold"], variable=self.key_mode_var).pack(pady=5)
        
        self.hold_dur = ctk.CTkEntry(self.key_frame, placeholder_text="Hold Time (ms)")
        self.hold_dur.insert(0, "100")
        self.hold_dur.pack(pady=2)

        # Toggle Switch
        def toggle_action():
            if self.action_type.get() == "mouse":
                self.key_frame.pack_forget()
                self.mouse_frame.pack(pady=5)
            else:
                self.mouse_frame.pack_forget()
                self.key_frame.pack(pady=5)

        ctk.CTkSegmentedButton(tab, values=["mouse", "key"], variable=self.action_type, command=lambda v: toggle_action()).pack(pady=5)

        # Start
        self.start_btn = ctk.CTkButton(tab, text="START CLICKER (F6)", command=lambda: self.toggle_running('clicker'), height=50, fg_color="#00C853", hover_color="#00E676")
        self.start_btn.pack(pady=30, padx=20, fill="x")

    # --- RECORDER TAB ---
    def setup_recorder_tab(self):
        tab = self.tab_recorder
        
        ctk.CTkLabel(tab, text="Record Actions").pack(pady=10)
        
        self.rec_status_lbl = ctk.CTkLabel(tab, text="Ready to Record", text_color="gray")
        self.rec_status_lbl.pack()

        # Controls
        btn_row = ctk.CTkFrame(tab, fg_color="transparent")
        btn_row.pack(pady=10)
        self.rec_btn = ctk.CTkButton(btn_row, text="REC (F7)", width=80, fg_color="#D50000", hover_color="#FF1744", command=lambda: self.toggle_recording(from_ui=True))
        self.rec_btn.pack(side="left", padx=5)
        
        ctk.CTkButton(btn_row, text="Save", width=80, command=self.save_macro).pack(side="left", padx=5)
        ctk.CTkButton(btn_row, text="Load", width=80, command=self.load_macro).pack(side="left", padx=5)

        # Settings
        sett_frame = ctk.CTkFrame(tab)
        sett_frame.pack(pady=10, fill="x", padx=10)
        
        self.straight_line = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(sett_frame, text="Smart Move (Straight Lines)", variable=self.straight_line).pack(pady=5)
        
        ctk.CTkLabel(sett_frame, text="Speed Multiplier").pack()
        self.speed_mult = ctk.CTkSlider(sett_frame, from_=0.5, to=5.0, number_of_steps=9)
        self.speed_mult.set(1.0)
        self.speed_mult.pack(pady=5)
        
        ctk.CTkLabel(sett_frame, text="Repeats (0 = Infinite)").pack()
        self.rec_repeats = ctk.CTkEntry(sett_frame, width=80)
        self.rec_repeats.insert(0, "1")
        self.rec_repeats.pack(pady=5)
        
        # Play
        self.play_rec_btn = ctk.CTkButton(tab, text="PLAY MACRO (F6)", command=lambda: self.toggle_running('macro'), height=50, fg_color="#2962FF", hover_color="#448AFF")
        self.play_rec_btn.pack(pady=(20, 10), padx=20, fill="x")

        # Visual Editor
        ctk.CTkLabel(tab, text="Macro Timeline (Visual Editor)").pack(anchor="w", padx=20)
        self.event_list_frame = ctk.CTkScrollableFrame(tab, height=200, label_text="Recorded Events")
        self.event_list_frame.pack(fill="both", expand=True, padx=10, pady=10)
        self.refresh_event_list()

    # --- IMAGE SEARCH TAB ---
    def setup_image_tab(self):
        tab = self.tab_img
        
        ctk.CTkLabel(tab, text="Image Recognition").pack(pady=10)
        
        self.img_path = ctk.StringVar()
        ctk.CTkEntry(tab, textvariable=self.img_path, placeholder_text="Path to image...").pack(pady=5, padx=20, fill="x")
        
        btn_box = ctk.CTkFrame(tab, fg_color="transparent")
        btn_box.pack(pady=5)
        
        ctk.CTkButton(btn_box, text="Browse Image", width=120, command=self.browse_image).grid(row=0, column=0, padx=5)
        ctk.CTkButton(btn_box, text="Paste Clipboard", width=120, fg_color="#E65100", hover_color="#EF6C00", command=self.paste_image).grid(row=0, column=1, padx=5)
        
        ctk.CTkLabel(tab, text="Check Interval (ms)").pack(pady=(10,0))
        self.img_interval = ctk.CTkEntry(tab, width=100)
        self.img_interval.insert(0, "1000")
        self.img_interval.pack(pady=5)
        
        ctk.CTkLabel(tab, text="Confidence (0.0 - 1.0)").pack(pady=(10,0))
        self.img_conf = ctk.CTkSlider(tab, from_=0.5, to=0.99)
        self.img_conf.set(0.8)
        self.img_conf.pack(pady=5)

        self.start_img_btn = ctk.CTkButton(tab, text="START SEARCH (F6)", command=lambda: self.toggle_running('image'), height=50, fg_color="#AA00FF", hover_color="#D500F9")
        self.start_img_btn.pack(pady=30, padx=20, fill="x")

    # --- LOGIC ---
    def refresh_event_list(self):
        # Clear existing
        try:
            for widget in self.event_list_frame.winfo_children():
                widget.destroy()
        except: pass

        events = self.recorder.events
        if not events:
            ctk.CTkLabel(self.event_list_frame, text="No events recorded").pack()
            return

        # Optimization: Filter out 'move' events and limit display count
        # Showing thousands of move events freezes the UI
        indexed_events = list(enumerate(events))
        # Filter out moves for visibility (they are clutter usually)
        display_list = [(i, e) for i, e in indexed_events if e['type'] != 'move']
        
        MAX_DISPLAY = 50
        truncated = False
        if len(display_list) > MAX_DISPLAY:
             display_list = display_list[:MAX_DISPLAY]
             truncated = True

        for idx, ev in display_list:
            row = ctk.CTkFrame(self.event_list_frame)
            row.pack(fill="x", pady=2)
            
            # Type Label
            t_str = ev['type'].upper().replace('_', ' ')
            if 'click' in t_str.lower(): color = "#00C853" if ev.get('pressed') else "#00E676"
            elif 'key' in t_str.lower(): color = "#2962FF"
            else: color = "gray"
            
            ctk.CTkLabel(row, text=f"#{idx+1}", width=30).pack(side="left", padx=5)
            ctk.CTkLabel(row, text=t_str, text_color=color, width=80).pack(side="left", padx=5)
            
            # Details
            details = ""
            if ev['type'] == 'click':
                details = f"{ev['button']} ({ev['x']}, {ev['y']})"
            elif 'key' in ev['type']:
                details = f"Key: {ev['key']}"
            elif ev['type'] == 'scroll':
                details = f"Scroll {ev['dy']}"
                
            ctk.CTkLabel(row, text=details, anchor="w").pack(side="left", fill="x", expand=True, padx=5)
            
            # Delete Btn
            def delete_evt(real_idx=idx):
                if real_idx < len(self.recorder.events):
                    del self.recorder.events[real_idx]
                    self.refresh_event_list()
                    self.rec_status_lbl.configure(text=f"Recorded {len(self.recorder.events)} events")
                
            ctk.CTkButton(row, text="X", width=30, fg_color="#D50000", hover_color="red", command=delete_evt).pack(side="right", padx=5)
            
        if truncated:
            ctk.CTkLabel(self.event_list_frame, text=f"... and more (hidden for performance)", text_color="orange").pack()
        elif len(events) > len(display_list):
             ctk.CTkLabel(self.event_list_frame, text=f"(Mouse movements hidden)", text_color="gray", font=("Arial", 10)).pack()

    def browse_image(self):
        path = filedialog.askopenfilename(filetypes=[("Images", "*.png;*.jpg;*.jpeg")])
        if path: self.img_path.set(path)

    def paste_image(self):
        try:
            from PIL import ImageGrab
            img = ImageGrab.grabclipboard()
            if img:
                # Save to a generic location
                path = "pasted_target.png"
                img.save(path)
                self.img_path.set(path)
                messagebox.showinfo("Success", "Image pasted from clipboard!")
            else:
                messagebox.showwarning("No Image", "No image found in clipboard.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to paste: {e}")

    def toggle_rec_hotkey(self):
        self.after(0, lambda: self.toggle_recording(from_ui=False))

    def toggle_recording(self, from_ui=True):
        if not self.recorder.recording:
            # Start
            self.recorder.start()
            self.rec_btn.configure(text="STOP (F7)")
            self.rec_status_lbl.configure(text="Recording...", text_color="red")
        else:
            # Stop
            self.recorder.stop(remove_last_click=from_ui)
            self.rec_btn.configure(text="REC (F7)")
            self.rec_status_lbl.configure(text=f"Recorded {len(self.recorder.events)} events", text_color="white")
            self.refresh_event_list()

    def save_macro(self):
        if not self.recorder.events: return
        path = filedialog.asksaveasfilename(defaultextension=".json")
        if path:
            with open(path, 'w') as f: json.dump(self.recorder.events, f)

    def load_macro(self):
        path = filedialog.askopenfilename(filetypes=[("JSON", "*.json")])
        if path:
            with open(path, 'r') as f: 
                self.recorder.events = json.load(f)
                self.rec_status_lbl.configure(text=f"Loaded {len(self.recorder.events)} events")
                self.refresh_event_list()

    def toggle_via_hotkey(self):
        # Schedule in main thread
        self.after(0, self._handle_hotkey)

    def _handle_hotkey(self):
        if self.running:
            self.stop_all()
        else:
            # Start based on active tab
            tab = self.tab_view.get()
            if tab == "Autoclicker":
                self.start_mode('clicker')
            elif tab == "Recorder":
                self.start_mode('macro')
            elif tab == "Image Search":
                self.start_mode('image')

    def stop_all(self):
        if self.running:
            self.running = False
            self.stop_event.set()
            self.status_label.configure(text="STOPPED", text_color="gray")
            # Reset btns
            self.start_btn.configure(text="START CLICKER (F6)", fg_color="#00C853")
            self.play_rec_btn.configure(text="PLAY MACRO (F6)", state="normal")
            self.start_img_btn.configure(text="START SEARCH (F6)", state="normal")

    def toggle_running(self, mode):
        if self.running:
            self.stop_all()
        else:
            self.start_mode(mode)

    def start_mode(self, mode):
        self.stop_event.clear()
        
        args = ()
        target = None
        
        if mode == 'clicker':
            interval = self.get_interval()
            target = self.run_clicker
            args = (interval,)
            self.start_btn.configure(text="STOP (F6)", fg_color="#D50000")
            
        elif mode == 'macro':
            if not self.recorder.events: 
                messagebox.showwarning("Empty", "No macro recorded!")
                return
            target = self.run_macro
            self.play_rec_btn.configure(text="STOP (F6)")
            
        elif mode == 'image':
            if not self.img_path.get(): 
                messagebox.showwarning("Missing Image", "Please select or paste an image first.")
                return
            target = self.run_image_search
            self.start_img_btn.configure(text="STOP (F6)")

        if target:
            self.running = True
            self.status_label.configure(text=f"RUNNING: {mode.upper()}", text_color="#00FF00")
            self.click_thread = threading.Thread(target=target, args=args, daemon=True)
            self.click_thread.start()

    def get_interval(self):
        try:
            h = int(self.inputs['hours'].get() or 0)
            m = int(self.inputs['mins'].get() or 0)
            s = int(self.inputs['secs'].get() or 0)
            ms = int(self.inputs['ms'].get() or 0)
            val = (h * 3600) + (m * 60) + s + (ms / 1000)
            return max(val, 0.01)
        except: return 1.0

    # --- THREAD LOOPS ---
    def run_clicker(self, interval):
        while not self.stop_event.is_set():
            # Action
            act = self.action_type.get()
            if act == "mouse":
                btn = getattr(Button, self.click_btn_var.get())
                count = 2 if self.click_type_var.get() == 'double' else 1
                self.mouse.click(btn, count)
            elif act == "key":
                k_val = self.key_entry.get()
                if k_val:
                    key = self.resolve_key(k_val)
                    if key:
                        self.keyboard.press(key)
                        if self.key_mode_var.get() == "hold":
                            try:
                                dur = int(self.hold_dur.get() or 100) / 1000
                                time.sleep(dur)
                            except: pass
                        self.keyboard.release(key)

            # Smart Sleep
            end = time.time() + interval
            while time.time() < end:
                if self.stop_event.is_set(): return
                time.sleep(0.01)

    def run_image_search(self):
        img_path = self.img_path.get()
        interval = int(self.img_interval.get() or 1000) / 1000
        conf = self.img_conf.get()
        
        while not self.stop_event.is_set():
            try:
                # grayscale=True speeds up search significantly
                pos = pyautogui.locateCenterOnScreen(img_path, confidence=conf, grayscale=True)
                if pos:
                    pyautogui.click(pos)
                    # Move away so cursor doesn't block detection next time
                    pyautogui.moveTo(10, 10)
                    print(f"Clicked image at {pos}")
            except Exception as e:
                # pyscreeze.ImageNotFoundException is common, we just ignore
                pass

            end = time.time() + interval
            while time.time() < end:
                if self.stop_event.is_set(): return
                time.sleep(0.1)

    def run_macro(self):
        events = self.recorder.events
        speed = self.speed_mult.get()
        
        try:
            repeats = int(self.rec_repeats.get())
        except: repeats = 1
        
        count = 0
        while not self.stop_event.is_set():
            if repeats > 0 and count >= repeats: break
            
            start_t = events[0]['time']
            real_start = time.time()
            
            for i, ev in enumerate(events):
                if self.stop_event.is_set(): break
                
                # Timing
                target_time = (ev['time'] - start_t) / speed
                current_run_time = time.time() - real_start
                wait = target_time - current_run_time
                if wait > 0: time.sleep(wait)
                
                # Action
                type = ev['type']
                if type == 'move':
                    if not self.straight_line.get():
                        self.mouse.position = (ev['x'], ev['y'])
                        
                elif type == 'click':
                    if self.straight_line.get():
                       pyautogui.moveTo(ev['x'], ev['y'], duration=0.1) 
                    
                    btn = getattr(Button, ev['button'])
                    if ev['pressed']: self.mouse.press(btn)
                    else: self.mouse.release(btn)
                    
                elif type == 'scroll':
                    self.mouse.scroll(ev['dx'], ev['dy'])
                    
                elif type == 'key_press':
                    key = self.resolve_key(ev['key'])
                    if key: self.keyboard.press(key)
                    
                elif type == 'key_release':
                    key = self.resolve_key(ev['key'])
                    if key: self.keyboard.release(key)
            
            count += 1
            
        # Finished naturally, reset UI
        if not self.stop_event.is_set():
            self.after(0, self.stop_all)
                
    def resolve_key(self, key_str):
        # Basic mapping, pynput stores keys often as strings
        if len(key_str) == 1: return key_str
        try: return getattr(Key, key_str.replace('Key.', ''))
        except: return None
        
    def on_close(self):
        self.stop_all()
        self.recorder.stop()
        self.listener.stop()
        self.destroy()

if __name__ == "__main__":
    app = AutoclickerApp()
    app.protocol("WM_DELETE_WINDOW", app.on_close)
    app.mainloop()
