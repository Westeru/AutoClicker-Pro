import time
import json
from typing import Callable, Optional
import pyautogui
from pynput.mouse import Button, Controller as MouseController
from pynput.keyboard import Controller as KeyboardController

pyautogui.PAUSE = 0.0

_genai = None
_genai_types = None


def get_genai():
    global _genai, _genai_types
    if _genai is None:
        try:
            from google import genai
            from google.genai import types
            _genai = genai
            _genai_types = types
        except ImportError:
            _genai = False
            _genai_types = None
    return _genai if _genai is not False else None


class AIController:
    def __init__(self, api_key: Optional[str], stop_event):
        self.api_key = api_key
        self.stop_event = stop_event
        self.mouse = MouseController()
        self.keyboard = KeyboardController()
        self._client = None

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

    def execute_prompt(self, prompt: str, max_steps: int = 8, callback: Optional[Callable[[str], None]] = None) -> bool:
        genai = get_genai()
        if not genai:
            if callback:
                callback("Error: google-genai is not installed.")
            print("google-genai is not installed.")
            return False

        if not self.api_key:
            if callback:
                callback("Error: No Gemini API key provided.")
            print("No Gemini API key provided.")
            return False

        if self._client is None:
            self._client = genai.Client(api_key=self.api_key)

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
                if callback:
                    callback(msg)

                gen_config = (
                    _genai_types.GenerateContentConfig(temperature=0.0)
                    if _genai_types is not None
                    else {"temperature": 0.0}
                )

                response = self._client.models.generate_content(
                    model='gemini-2.5-flash',
                    contents=[
                        self.system_prompt,
                        f"GOAL: {prompt}",
                        screenshot
                    ],
                    config=gen_config,
                )

                # Parse response
                text = (response.text or "").strip()
                if text.startswith('```json'):
                    text = text[7:]
                elif text.startswith('```'):
                    text = text[3:]
                if text.endswith('```'):
                    text = text[:-3]
                text = text.strip()

                action_data = json.loads(text)

                action = action_data.get("action")
                msg = f"Decided Action: {action_data}"
                print(msg)
                if callback:
                    callback(msg)

                if action == "DONE":
                    msg = "Goal completed successfully!"
                    print(msg)
                    if callback:
                        callback(msg)
                    return True
                elif action == "CLICK":
                    x = int(action_data.get("x", 0))
                    y = int(action_data.get("y", 0))
                    btn_str = action_data.get("button", "left")
                    btn = getattr(Button, btn_str, Button.left)
                    pyautogui.moveTo(x, y)
                    self.mouse.position = (x, y)
                    self.mouse.click(btn, 1)
                elif action == "TYPE":
                    text_to_type = action_data.get("text", "")
                    pyautogui.write(text_to_type, interval=0.03)
                elif action == "PRESS":
                    key = action_data.get("key", "")
                    if key.lower() in ['win', 'windows']:
                        pyautogui.press('win')
                    else:
                        pyautogui.press(key)
                else:
                    msg = f"Unknown AI action: {action}"
                    print(msg)
                    if callback:
                        callback(msg)

            except Exception as e:
                msg = f"AI Action Error: {e}"
                print(msg)
                if callback:
                    callback(msg)
                time.sleep(0.5)

            # Wait briefly for screen to update before next step
            time.sleep(0.6)

        msg = f"Failed to complete goal within {max_steps} steps."
        print(msg)
        if callback:
            callback(msg)
        return False
