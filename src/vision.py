import random
import time
from typing import Any, Callable, Dict, Optional
import cv2
import numpy as np
import pyautogui
from PIL import ImageGrab

# Eliminate default 100ms pause per PyAutoGUI call for faster clicking & movement
pyautogui.PAUSE = 0.0


class ImageSearcher:
    def __init__(
        self,
        stop_event,
        update_callback: Optional[Callable[[float], None]] = None,
        on_click_callback: Optional[Callable[[], None]] = None,
    ):
        self.stop_event = stop_event
        self.update_callback = update_callback  # Function to call with match confidence
        self.on_click_callback = on_click_callback  # Function called after each match click

    def run(self, config: Dict[str, Any]) -> None:
        """
        config:
        - img_path (str)
        - interval (float) sec
        - confidence (float)
        - grayscale (bool)
        - monitor_rect (optional tuple/list of (left, top, right, bottom))
        - roi_rect (optional tuple/list of (left, top, right, bottom) — overrides monitor_rect)
        - return_cursor (bool)
        - cooldown (float) extra seconds to wait after clicking a match
        - pos_jitter_px (int) optional +/- random pixel offset
        """
        img_path = config.get('img_path')
        interval = float(config.get('interval', 1.0))
        conf = float(config.get('confidence', 0.8))
        use_gray = bool(config.get('grayscale', True))
        roi_rect = config.get('roi_rect')
        monitor_rect = config.get('monitor_rect')
        return_cursor = bool(config.get('return_cursor', True))
        cooldown = max(0.0, float(config.get('cooldown', 0.0)))
        pos_jitter_px = max(0, int(config.get('pos_jitter_px', 0)))

        # Pre-load template once outside the loop
        try:
            template = cv2.imread(img_path)
            if template is None:
                print(f"Failed to load image: {img_path}")
                return
            if use_gray:
                template = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)
            t_h, t_w = template.shape[:2]
            half_w, half_h = t_w // 2, t_h // 2
        except Exception as e:
            print(f"Error loading template: {e}")
            return

        active_rect = roi_rect if roi_rect else monitor_rect
        bbox = tuple(int(v) for v in active_rect) if active_rect else None
        offset_x = bbox[0] if bbox else 0
        offset_y = bbox[1] if bbox else 0
        is_stopped = self.stop_event.is_set

        while not is_stopped():
            matched_this_cycle = False
            try:
                # Capture selected ROI / monitor (or primary via pyautogui when None)
                if bbox is not None:
                    screenshot = ImageGrab.grab(bbox=bbox, all_screens=True)
                else:
                    screenshot = pyautogui.screenshot()
                screen_np = np.array(screenshot)

                # Convert color for OpenCV
                screen_bgr = cv2.cvtColor(screen_np, cv2.COLOR_RGB2BGR)

                check_img = screen_bgr
                if use_gray:
                    check_img = cv2.cvtColor(screen_bgr, cv2.COLOR_BGR2GRAY)

                # Match template
                res = cv2.matchTemplate(check_img, template, cv2.TM_CCOEFF_NORMED)
                _, max_val, _, max_loc = cv2.minMaxLoc(res)

                # Update UI callback
                if self.update_callback:
                    self.update_callback(max_val)

                if max_val >= conf:
                    center_x = offset_x + max_loc[0] + half_w
                    center_y = offset_y + max_loc[1] + half_h
                    if pos_jitter_px > 0:
                        center_x += random.randint(-pos_jitter_px, pos_jitter_px)
                        center_y += random.randint(-pos_jitter_px, pos_jitter_px)

                    orig_pos = pyautogui.position() if return_cursor else None
                    pyautogui.click(center_x, center_y)
                    if return_cursor and orig_pos is not None:
                        pyautogui.moveTo(orig_pos[0], orig_pos[1])
                    else:
                        # Move away so cursor doesn't block detection next time
                        pyautogui.moveTo(offset_x + 10, offset_y + 10)
                    matched_this_cycle = True
                    if self.on_click_callback:
                        self.on_click_callback()
                    print(f"Clicked image at ({center_x}, {center_y}) with conf {max_val:.2f}")

            except Exception as e:
                print(f"Search loop error: {e}")

            wait_time = interval + (cooldown if matched_this_cycle else 0.0)
            end = time.time() + wait_time
            while time.time() < end:
                if is_stopped():
                    return
                remaining = end - time.time()
                if remaining <= 0:
                    break
                time.sleep(min(0.05, max(0.005, remaining)))
