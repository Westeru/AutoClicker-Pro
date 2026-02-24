import time
import json
import pyautogui
from pynput.mouse import Button, Controller as MouseController
from pynput.keyboard import Controller as KeyboardController

try:
    from google import genai
    from google.genai import types
except ImportError:
    genai = None

class AIController:
    def __init__(self, api_key, stop_event):
        self.api_key = api_key
        self.stop_event = stop_event
        self.mouse = MouseController()
        self.keyboard = KeyboardController()
        
        self.system_prompt = """You are an autonomous AI Agent controlling a user's computer to achieve a specific GOAL.
You will be provided with a screenshot of the current screen and the user's GOAL.

Based on the screenshot, you must decide the NEXT SINGLE ACTION to take to progress towards the GOAL.

You must respond ONLY with a JSON object containing the action. Do not include any markdown formatting or conversational text.

Available Actions:
1. {"action": "CLICK", "x": [integer], "y": [integer], "button": "left"|"right"|"middle"} 
   - Use this to click on a specific coordinate on the screen.
2. {"action": "TYPE", "text": "[string]"}
   - Use this to type out a sequence of characters.
3. {"action": "PRESS", "key": "[string]"}
   - Use this to press a specific key (e.g. "enter", "win", "esc").
4. {"action": "DONE"}
   - Use this when the GOAL has been successfully achieved.

IMPORTANT RULES:
- If the GOAL is "Open Notepad", you should first output a PRESS action for the "win" key (to open the start menu), wait for the next screenshot, then TYPE "Notepad", wait for the next screenshot, and finally PRESS "enter".
- Do not hallucinate coordinates. Look carefully at the provided image to determine where elements are.
- Output ONLY the JSON object.
"""

    def execute_prompt(self, prompt, max_steps=8, callback=None):
        if not genai:
            if callback: callback("Error: google-genai is not installed.")
            print("google-genai is not installed.")
            return False
            
        if not self.api_key:
            if callback: callback("Error: No Gemini API key provided.")
            print("No Gemini API key provided.")
            return False
            
        client = genai.Client(api_key=self.api_key)
        
        for step in range(max_steps):
            if self.stop_event.is_set():
                print("AI Action aborted by user (Panic Button).")
                return False
                
            # Take screenshot
            screenshot = pyautogui.screenshot()
            
            # Call Gemini
            try:
                msg = f"Step {step+1}/{max_steps}: Analyzing screen for goal '{prompt}'..."
                print(msg)
                if callback: callback(msg)
                
                response = client.models.generate_content(
                    model='gemini-2.5-flash',
                    contents=[
                        self.system_prompt,
                        f"GOAL: {prompt}",
                        screenshot
                    ],
                    config=types.GenerateContentConfig(
                        temperature=0.0,
                    )
                )
                
                # Parse response
                text = response.text.strip()
                if text.startswith('```json'):
                    text = text[7:]
                if text.endswith('```'):
                    text = text[:-3]
                text = text.strip()
                
                action_data = json.loads(text)
                
                action = action_data.get("action")
                msg = f"Decided Action: {action_data}"
                print(msg)
                if callback: callback(msg)
                
                if action == "DONE":
                    msg = "Goal completed successfully!"
                    print(msg)
                    if callback: callback(msg)
                    return True
                elif action == "CLICK":
                    x = action_data.get("x", 0)
                    y = action_data.get("y", 0)
                    btn_str = action_data.get("button", "left")
                    btn = getattr(Button, btn_str, Button.left)
                    pyautogui.moveTo(x, y)
                    self.mouse.position = (x, y)
                    self.mouse.click(btn, 1)
                elif action == "TYPE":
                    text_to_type = action_data.get("text", "")
                    pyautogui.write(text_to_type, interval=0.05)
                elif action == "PRESS":
                    key = action_data.get("key", "")
                    if key.lower() in ['win', 'windows']:
                        pyautogui.press('win')
                    else:
                        pyautogui.press(key)
                else:
                    msg = f"Unknown AI action: {action}"
                    print(msg)
                    if callback: callback(msg)
                
            except Exception as e:
                msg = f"AI Action Error: {e}"
                print(msg)
                if callback: callback(msg)
                time.sleep(1) # wait a bit on error
            
            # Wait a moment for screen to update before next step
            time.sleep(1.0)
            
        msg = f"Failed to complete goal within {max_steps} steps."
        print(msg)
        if callback: callback(msg)
        return False
