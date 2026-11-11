import time
from typing import Any, Dict, Optional
from pynput.mouse import Button, Controller as MouseController
from pynput.keyboard import Key, Controller as KeyboardController


class Clicker:
    def __init__(self, stop_event):
        self.stop_event = stop_event
        self.mouse = MouseController()
        self.keyboard = KeyboardController()

    def resolve_key(self, key_str: str) -> Optional[Any]:
        if not key_str:
            return None
        if len(key_str) == 1:
            return key_str
        try:
            return getattr(Key, key_str.replace('Key.', ''))
        except AttributeError:
            return None

    def run(self, config: Dict[str, Any]) -> None:
        """
        High-speed clicker loop with pre-resolved configuration.
        config dict:
        - interval (float)
        - action_type (str): 'mouse' or 'key'
        - mouse_btn (str): 'left', 'right', 'middle'
        - click_type (str): 'single', 'double'
        - key (str): key to press
        - key_mode (str): 'press', 'hold'
        """
        interval = float(config.get('interval', 1.0))
        act = config.get('action_type', 'mouse')

        # Pre-resolve mouse & key parameters outside the hot loop
        btn = None
        count = 1
        key = None
        is_hold = False

        if act == "mouse":
            btn_str = config.get('mouse_btn', 'left')
            btn = getattr(Button, btn_str, None)
            count = 2 if config.get('click_type') == 'double' else 1
        elif act == "key":
            k_val = config.get('key')
            if k_val:
                key = self.resolve_key(k_val)
                is_hold = (config.get('key_mode') == 'hold')

        mouse_click = self.mouse.click
        kb_press = self.keyboard.press
        kb_release = self.keyboard.release
        is_stopped = self.stop_event.is_set

        while not is_stopped():
            if act == "mouse":
                if btn is not None:
                    mouse_click(btn, count)
            elif act == "key":
                if key is not None:
                    if is_hold:
                        kb_press(key)
                        while not is_stopped():
                            time.sleep(0.02)
                        kb_release(key)
                        return
                    else:
                        kb_press(key)
                        kb_release(key)

            # Adaptive high-precision sleep
            end = time.time() + interval
            while time.time() < end:
                if is_stopped():
                    return
                remaining = end - time.time()
                if remaining <= 0:
                    break
                time.sleep(min(0.01, max(0.001, remaining)))
