import time
from pynput import keyboard as pynput_keyboard
from pynput import mouse as pynput_mouse
from pynput.keyboard import Key

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
