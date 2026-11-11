import time
from typing import Any, Callable, Dict, Optional
import cv2
import numpy as np
import pyautogui

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
        """
        img_path = config.get('img_path')
        interval = float(config.get('interval', 1.0))
        conf = float(config.get('confidence', 0.8))
        use_gray = bool(config.get('grayscale', True))

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

        is_stopped = self.stop_event.is_set

        while not is_stopped():
            try:
                # Capture screen
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
                    center_x = max_loc[0] + half_w
                    center_y = max_loc[1] + half_h

                    pyautogui.click(center_x, center_y)
                    # Move away so cursor doesn't block detection next time
                    pyautogui.moveTo(10, 10)
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
