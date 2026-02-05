import cv2
import numpy as np
import pyautogui
import time
import threading

class ImageSearcher:
    def __init__(self, stop_event, update_callback=None):
        self.stop_event = stop_event
        self.update_callback = update_callback # Function to call with match confidence
        
    def run(self, config):
        """
        config:
        - img_path (str)
        - interval (float) sec
        - confidence (float)
        - grayscale (bool)
        """
        img_path = config.get('img_path')
        interval = config.get('interval', 1.0)
        conf = config.get('confidence', 0.8)
        use_gray = config.get('grayscale', True)
        
        # Pre-load template
        try:
            template = cv2.imread(img_path)
            if template is None:
                print(f"Failed to load image: {img_path}")
                return
            if use_gray:
                template = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)
            t_h, t_w = template.shape[:2]
        except Exception as e:
            print(f"Error loading template: {e}")
            return
        
        while not self.stop_event.is_set():
            try:
                # Capture screen
                screenshot = pyautogui.screenshot()
                screen_np = np.array(screenshot)
                
                # Convert color for OpenCV
                screen_bgr = cv2.cvtColor(screen_np, cv2.COLOR_RGB2BGR)
                
                check_img = screen_bgr
                if use_gray:
                    check_img = cv2.cvtColor(screen_bgr, cv2.COLOR_BGR2GRAY)
                
                # Match
                res = cv2.matchTemplate(check_img, template, cv2.TM_CCOEFF_NORMED)
                min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)
                
                # Update UI callback
                if self.update_callback:
                    self.update_callback(max_val)
                
                if max_val >= conf:
                    # Click center
                    top_left = max_loc
                    center_x = top_left[0] + t_w // 2
                    center_y = top_left[1] + t_h // 2
                    
                    pyautogui.click(center_x, center_y)
                    # Move away so cursor doesn't block detection next time
                    pyautogui.moveTo(10, 10)
                    print(f"Clicked image at ({center_x}, {center_y}) with conf {max_val:.2f}")

            except Exception as e:
                print(f"Search loop error: {e}")
                pass

            end = time.time() + interval
            while time.time() < end:
                if self.stop_event.is_set(): return
                time.sleep(0.1)
