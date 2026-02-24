# AutoClicker-Pro AI Guidelines

## 1. Project Overview
- **Name**: AutoClicker-Pro
- **Type**: Desktop Automation Application
- **Core Purpose**: Advanced autoclicker with macro recording, visual workflow building, and image recognition capabilities.
- **Entry Point**: `src/main.py`
- **Build System**: PyInstaller (configured via `AutoclickerPro.spec`)

## 2. Tech Stack
- **Language**: Python 3
- **UI Framework**: `PySide6` (Modern Qt bindings)
- **Automation Libraries**: `pyautogui`, `pynput`
- **Image Processing**: `opencv-python`, `Pillow`
- **AI Integration**: `google-genai`
- **Packaging**: `pyinstaller`

## 3. Architecture & Directory Structure
- All source code MUST be placed in the `src/` directory.
- Maintain a strict separation of concerns:
  - **`main.py`**: User Interface (UI) definitions, event bindings, and app lifecycle management.
  - **`clicker.py`**: Core clicking and keyboard automation logic.
  - **`recorder.py`**: Macro recording and replay logic.
  - **`vision.py`**: Image recognition logic (OpenCV template matching, etc.).
  - **`workflow_runner.py`**: Visual workflow/playlist execution logic.
  - **`ai_controller.py`**: Gemini API integration for autonomous AI workflow actions.

## 4. Coding Standards & Best Practices
### Python Convention
- Follow **PEP 8** guidelines for code formatting.
- Use **Type Hints** (`typing` module) for function signatures and critical variables to improve readability and AI context.
- Keep functions small, testable, and focused on a single task.

### UI Development (PySide6)
- Utilize PySide6's signal/slot mechanism architecture for communicating between background execution threads and the main GUI thread.
- Maintain the existing dark theme aesthetic using QSS stylesheets.
- Ensure UI operations do not block the main thread. Heavy processing or infinite clicking loops should be offloaded to separate threads using `QThread`.

### Automation & Hotkeys
- Global hotkeys (e.g., F6, F7) are managed via `pynput.keyboard`. Ensure that listener threads are properly managed and closed cleanly upon app exit.
- `pyautogui` operations should have fail-safes enabled.

## 5. Build and Deployment
- The standalone executable is built using PyInstaller.
- **Rule**: If you add any non-code assets (images, icons, sound files) or new pip packages, you MUST update `AutoclickerPro.spec` and `requirements.txt` respectively.
- Never write temporary files to the `src/` directory. Use the user's `AppData` or the current execution directory context provided by PyInstaller (`sys._MEIPASS`).

## 6. Git and Version Control
- Commit messages should be clear and descriptive.
- Do not commit `/dist/`, `/build/`, or `__pycache__` folders. Use `.gitignore` appropriately.
