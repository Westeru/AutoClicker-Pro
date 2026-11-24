import random
import time
from typing import Any, Callable, Dict, Optional
from pynput.mouse import Button, Controller as MouseController
from pynput.keyboard import Key, Controller as KeyboardController


class Clicker:
    def __init__(self, stop_event, on_click_callback: Optional[Callable[[], None]] = None):
        self.stop_event = stop_event
        self.on_click_callback = on_click_callback
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
        - interval (float): seconds between actions
        - action_type (str): 'mouse' or 'key'
        - mouse_btn (str): 'left', 'right', 'middle'
        - click_type (str): 'single', 'double'
        - key (str): key to press
        - key_mode (str): 'press', 'hold'
        - repeat_count (int): 0 = infinite, >0 = exact number of actions
        - jitter_ms (int): +/- random timing jitter in milliseconds
        - fixed_pos (tuple[int, int] | None): optional fixed click coordinates
        - pos_jitter_px (int): +/- random pixel offset around click position
        - return_cursor (bool): return cursor to original position after fixed-pos click
        """
        interval = float(config.get('interval', 1.0))
        act = config.get('action_type', 'mouse')
        repeat_count = int(config.get('repeat_count', 0))
        jitter_sec = max(0.0, float(config.get('jitter_ms', 0)) / 1000.0)
        fixed_pos = config.get('fixed_pos')
        pos_jitter_px = max(0, int(config.get('pos_jitter_px', 0)))
        return_cursor = bool(config.get('return_cursor', False))

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
        on_click = self.on_click_callback
        done_count = 0

        while not is_stopped():
            performed = False

            if act == "mouse":
                if btn is not None:
                    orig_pos = None
                    if fixed_pos is not None:
                        if return_cursor:
                            orig_pos = self.mouse.position
                        tx, ty = int(fixed_pos[0]), int(fixed_pos[1])
                        if pos_jitter_px > 0:
                            tx += random.randint(-pos_jitter_px, pos_jitter_px)
                            ty += random.randint(-pos_jitter_px, pos_jitter_px)
                        self.mouse.position = (tx, ty)
                    elif pos_jitter_px > 0:
                        cx, cy = self.mouse.position
                        self.mouse.position = (
                            cx + random.randint(-pos_jitter_px, pos_jitter_px),
                            cy + random.randint(-pos_jitter_px, pos_jitter_px),
                        )

                    mouse_click(btn, count)

                    if orig_pos is not None:
                        self.mouse.position = orig_pos
                    performed = True

            elif act == "key":
                if key is not None:
                    if is_hold:
                        kb_press(key)
                        if on_click:
                            on_click()
                        while not is_stopped():
                            time.sleep(0.02)
                        kb_release(key)
                        return
                    else:
                        kb_press(key)
                        kb_release(key)
                        performed = True

            if performed:
                done_count += 1
                if on_click:
                    on_click()
                if repeat_count > 0 and done_count >= repeat_count:
                    return

            # Compute current sleep duration (with optional random jitter)
            sleep_dur = interval
            if jitter_sec > 0.0:
                sleep_dur = max(0.001, interval + random.uniform(-jitter_sec, jitter_sec))

            # Adaptive high-precision sleep
            end = time.time() + sleep_dur
            while time.time() < end:
                if is_stopped():
                    return
                remaining = end - time.time()
                if remaining <= 0:
                    break
                time.sleep(min(0.01, max(0.001, remaining)))
