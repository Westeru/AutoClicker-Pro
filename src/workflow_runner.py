import time
import pyautogui
import cv2
import numpy as np
from pynput.mouse import Button, Controller as MouseController

class WorkflowRunner:
    def __init__(self, stop_event, highlight_callback=None, ai_debug_callback=None):
        self.stop_event = stop_event
        self.highlight_callback = highlight_callback
        self.ai_debug_callback = ai_debug_callback
        self.steps = []
        self.current_step_index = 0
        self.running = False
        self.mouse = MouseController()
        self.api_key = None
        
    def set_steps(self, steps):
        self.steps = steps
        
    def run(self):
        self.running = True
        self.current_step_index = 0
        
        while self.running and self.current_step_index < len(self.steps):
            if self.stop_event.is_set(): break
            
            step = self.steps[self.current_step_index]
            
            if self.highlight_callback:
                self.highlight_callback(self.current_step_index)
            
            try:
                self.execute_step(step)
            except Exception as e:
                print(f"Error in step {self.current_step_index}: {e}")
                
            self.current_step_index += 1
            # Small delay between steps
            time.sleep(0.1)
            
        self.running = False

    def execute_step(self, step):
        action = step.get('action')
        params = step.get('params', {})
        
        if action == 'Delay':
            time.sleep(float(params.get('duration', 1000)) / 1000.0)
            
        elif action == 'Click':
            x = int(params.get('x', 0))
            y = int(params.get('y', 0))
            btn_str = params.get('button', 'left')
            btn = getattr(Button, btn_str, Button.left)
            clicks = 2 if params.get('type') == 'double' else 1
            
            # Optional move
            pyautogui.moveTo(x, y) 
            # Pynput click
            self.mouse.position = (x, y)
            self.mouse.click(btn, clicks)
            
        elif action == 'Key Press':
            k_str = params.get('key', '')
            if k_str:
                keys = [k.strip().lower() for k in k_str.split('+')]
                keys = ['win' if k == 'windows' else k for k in keys]
                
                if len(keys) > 1:
                    pyautogui.hotkey(*keys)
                else:
                    pyautogui.press(keys[0])
                    
        elif action == 'Type Text':
            text = params.get('text', '')
            if text:
                pyautogui.write(text, interval=0.05)
                
        elif action == 'Wait Image':
            path = params.get('image_path')
            timeout = float(params.get('timeout', 10))
            threshold = float(params.get('confidence', 0.8))
            
            start = time.time()
            found = False
            while time.time() - start < timeout:
                if self.stop_event.is_set(): return
                pos = self._find_image(path, threshold)
                if pos:
                    found = True
                    break
                time.sleep(0.5)
            
            if not found:
                print(f"Workflow: Image not found '{path}' within timeout.")
                
        elif action == 'Click Image':
            path = params.get('image_path')
            timeout = float(params.get('timeout', 5))
            threshold = float(params.get('confidence', 0.8))
            btn_str = params.get('button', 'left')
            btn = getattr(Button, btn_str, Button.left)
            
            # Try to find
            start = time.time()
            pos = None
            while time.time() - start < timeout:
                if self.stop_event.is_set(): return
                pos = self._find_image(path, threshold)
                if pos: break
                time.sleep(0.2)
                
            if pos:
                self.mouse.position = pos
                self.mouse.click(btn, 1)
            else:
                print(f"Workflow: Image for click not found '{path}'")
                
        elif action == 'AI Action':
            from src.ai_controller import AIController
            prompt = params.get('prompt', '')
            if prompt:
                ai = AIController(self.api_key, self.stop_event)
                ai.execute_prompt(prompt, callback=self.ai_debug_callback)

    def _find_image(self, path, conf):
        try:
            if not path: return None
            
            template = cv2.imread(path)
            if template is None: return None
            
            screenshot = pyautogui.screenshot()
            screen_np = np.array(screenshot)
            screen_bgr = cv2.cvtColor(screen_np, cv2.COLOR_RGB2BGR)
            
            res = cv2.matchTemplate(screen_bgr, template, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, max_loc = cv2.minMaxLoc(res)
            
            if max_val >= conf:
                h, w = template.shape[:2]
                cx = max_loc[0] + w // 2
                cy = max_loc[1] + h // 2
                return (cx, cy)
        except Exception as e:
            print(f"Error finding image: {e}")
        return None
