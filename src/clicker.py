import time
import threading
from pynput.mouse import Button, Controller as MouseController
from pynput.keyboard import Key, Controller as KeyboardController

class Clicker:
    def __init__(self, stop_event):
        self.stop_event = stop_event
        self.mouse = MouseController()
        self.keyboard = KeyboardController()
        
    def resolve_key(self, key_str):
        if len(key_str) == 1: return key_str
        try: return getattr(Key, key_str.replace('Key.', ''))
        except AttributeError: return None

    def run(self, config):
        """
        config dict:
        - interval (float)
        - action_type (str): 'mouse' or 'key'
        - mouse_btn (str): 'left', 'right', 'middle'
        - click_type (str): 'single', 'double'
        - key (str): key to press
        - key_mode (str): 'press', 'hold'
        """
        interval = config.get('interval', 1.0)
        
        while not self.stop_event.is_set():
            act = config.get('action_type', 'mouse')
            
            if act == "mouse":
                btn_str = config.get('mouse_btn', 'left')
                btn = getattr(Button, btn_str, None)
                if btn is None:
                    continue
                count = 2 if config.get('click_type') == 'double' else 1
                self.mouse.click(btn, count)
                
            elif act == "key":
                k_val = config.get('key')
                if k_val:
                    key = self.resolve_key(k_val)
                    if key:
                        if config.get('key_mode') == 'hold':
                            self.keyboard.press(key)
                            while not self.stop_event.is_set():
                                time.sleep(0.03) # 30ms poll rate for stop event
                            self.keyboard.release(key)
                            return  # Hold mode exits when stop event fires
                        else:
                            self.keyboard.press(key)
                            self.keyboard.release(key)

            # Smart Sleep
            end = time.time() + interval
            while time.time() < end:
                if self.stop_event.is_set(): return
                time.sleep(0.01)
