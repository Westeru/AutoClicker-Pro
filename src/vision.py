import time
from typing import Any, Callable, Dict, Optional
import cv2
import numpy as np
import pyautogui
from PIL import ImageGrab

# Eliminate default 100ms pause per PyAutoGUI call for faster clicking & movement
pyautogui.PAUSE = 0.0


class ImageSearcher:
    def __init__(self, stop_event, update_callback: Optional[Callable[[float], None]] = None):
        self.stop_event = stop_event
        self.update_callback = update_callback  # Function to call with match confidence

    def run(self, config: Dict[str, Any]) -> None:
        """
        config:
        - img_path (str)
        - interval (float) sec
        - confidence (float)
        - grayscale (bool)
        - monitor_rect (optional tuple/list of (left, top, right, bottom))
        """
        img_path = config.get('img_path')
        interval = float(config.get('interval', 1.0))
        conf = float(config.get('confidence', 0.8))
        use_gray = bool(config.get('grayscale', True))
        monitor_rect = config.get('monitor_rect')
        return_cursor = bool(config.get('return_cursor', True))

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

        bbox = tuple(int(v) for v in monitor_rect) if monitor_rect else None
        offset_x = bbox[0] if bbox else 0
        offset_y = bbox[1] if bbox else 0
        is_stopped = self.stop_event.is_set

        while not is_stopped():
            try:
                # Capture selected monitor (or primary via pyautogui when None)
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

                    orig_pos = pyautogui.position() if return_cursor else None
                    pyautogui.click(center_x, center_y)
                    if return_cursor and orig_pos is not None:
                        pyautogui.moveTo(orig_pos[0], orig_pos[1])
                    else:
                        # Move away so cursor doesn't block detection next time
                        pyautogui.moveTo(offset_x + 10, offset_y + 10)
                    print(f"Clicked image at ({center_x}, {center_y}) with conf {max_val:.2f}")

            except Exception as e:
                print(f"Search loop error: {e}")

            end = time.time() + interval
            while time.time() < end:
                if is_stopped():
                    return
                remaining = end - time.time()
                if remaining <= 0:
                    break
                time.sleep(min(0.05, max(0.005, remaining)))
