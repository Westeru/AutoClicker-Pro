import time
from typing import Any, Dict, List
from pynput import keyboard as pynput_keyboard
from pynput import mouse as pynput_mouse
from pynput.keyboard import Key


class Recorder:
    def __init__(self):
        self.events: List[Dict[str, Any]] = []
        self.recording = False
        self.start_time = 0.0
        self._last_move_time = -1.0
        self.mouse_listener = None
        self.key_listener = None
        # Keys to ignore (Control keys)
        self.ignore_keys = []

    def start(self) -> None:
        self.events = []
        self.recording = True
        self.start_time = time.time()
        self._last_move_time = -1.0

        # Ignore F6 (Safety) and F7 (Record Toggle)
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

    def stop(self, remove_last_click: bool = False) -> None:
        self.recording = False
        if self.mouse_listener:
            self.mouse_listener.stop()
        if self.key_listener:
            self.key_listener.stop()

        if remove_last_click and self.events:
            # Remove the last click sequence (press and release) if near the end
            click_evs = [i for i, x in enumerate(self.events) if x['type'] == 'click']
            if len(click_evs) >= 2:
                last_idx = click_evs[-1]
                second_last = click_evs[-2]

                if last_idx > len(self.events) - 5:
                    self.events = self.events[:second_last]

    def _add_event(self, type: str, **kwargs) -> None:
        if not self.recording:
            return
        event = {
            "type": type,
            "time": time.time() - self.start_time,
            **kwargs
        }
        self.events.append(event)

    def on_move(self, x: int, y: int) -> None:
        if not self.recording:
            return
        elapsed = time.time() - self.start_time
        # Coalesce sub-8ms (125Hz+) mouse move bursts to prevent 1000Hz event bloat
        if (
            self.events
            and self.events[-1].get("type") == "move"
            and 0 <= (elapsed - self._last_move_time) < 0.008
        ):
            self.events[-1]["x"] = x
            self.events[-1]["y"] = y
            self.events[-1]["time"] = elapsed
            return
        self._last_move_time = elapsed
        self._add_event("move", x=x, y=y)

    def on_click(self, x: int, y: int, button, pressed: bool) -> None:
        btn_str = str(button).replace('Button.', '')
        self._add_event("click", x=x, y=y, button=btn_str, pressed=pressed)

    def on_scroll(self, x: int, y: int, dx: int, dy: int) -> None:
        self._add_event("scroll", x=x, y=y, dx=dx, dy=dy)

    def on_press(self, key) -> None:
        if key in self.ignore_keys:
            return
        try:
            k = key.char
        except AttributeError:
            k = str(key)
        self._add_event("key_press", key=k)

    def on_release(self, key) -> None:
        if key in self.ignore_keys:
            return
        try:
            k = key.char
        except AttributeError:
            k = str(key)
        self._add_event("key_release", key=k)
