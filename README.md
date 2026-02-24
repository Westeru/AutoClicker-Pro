# Autoclicker Pro

A modern, feature-rich Autoclicker built with Python and **PySide6**. Designed to be reliable, easy to use, and packed with advanced automation features including visual workflow building and **AI-Driven screen automation**.


<img width="593" height="723" alt="image" src="https://github.com/user-attachments/assets/7dc85ac6-8037-4fa4-b9bd-94094ab3c369" />

## Features

### 🖱️ Advanced Autoclicker
- **Precise Timing**: Set intervals in Hours, Minutes, Seconds, and Milliseconds.
- **Click Options**: Left, Right, Middle clicks. Single or Double types.
- **Key Press Mode**: Automate keyboard inputs (Press or Hold keys).
- **Modern UI**: Clean, dark-themed interface using `PySide6`.

### � Workflow Automation (Playlist)
- **Visual Builder**: Create complex automation sequences step-by-step.
- **Actions Supported**:
    - **Click**: Specify coordinates (X, Y) or use "Pick Pos" to capture mouse location.
    - **Key Press**: Press keys or combinations (e.g., `ctrl+c`, `win+r`).
    - **Type Text**: Type out long strings automatically.
    - **Wait/Delay**: Add precise pauses between actions.
    - **Image Actions**: Wait for an image to appear or Click on an image.
    - **🤖 AI Action**: Provide a natural language prompt (e.g. "Open Notepad") and let the Gemini Vision AI autonomously interact with your screen to achieve the goal.
- **Drag & Drop**: Easily reorder steps in your playlist using the `::` drag handle.
- **Edit & Save**: Edit existing steps, delete unwanted ones, and save your workflows to JSON files.

### �📼 Macro Recorder
- **Record & Replay**: Capture your mouse and keyboard actions and replay them instantly.
- **Smart Straight Lines**: Interpolate mouse movements to create perfectly straight lines during replay.
- **Repeat Counter**: Set specific repeat counts or loop infinitely.
- **Smart Stop**: Automatically excludes the "Stop" button click or Hotkey press from your recording.

### 🖼️ Image Recognition
- **Visual Automation**: Click buttons or elements based on their image.
- **Clipboard Paste**: Quickly snip a target and paste it directly into the app.
- **High Performance**: Optimized using OpenCV.

### ⌨️ Global Hotkeys
- **F6**: **Panic Button** (Stops everything) / Start Active Mode.
- **F7**: Toggle Recording.

## Project Structure

The project has been refactored for better maintainability:

```
root/
├── run.bat              # Quick start batch file
├── AutoclickerPro.spec  # PyInstaller Build Spec
├── src/                 # Source Code
│   ├── main.py          # Entry Point & UI
│   ├── clicker.py       # Autoclicker Logic
│   ├── recorder.py      # Recorder Logic
│   ├── vision.py        # Image Search Logic
│   ├── ai_controller.py # Gemini AI Logic
│   └── workflow_runner.py # Workflow/Playlist Logic
└── ...
```

## Running the App

### Option 1: Standalone Executable
If you have the built `.exe`:
1. Go to the `dist` folder.
2. Run `AutoclickerPro.exe`.

### Option 2: Quick Start (Source)
Double-click `run.bat` in the root directory.

### Option 3: Manual Run (Source)
1.  **Clone the repo**
    ```bash
    git clone https://github.com/Westeru/AutoClicker-Pro.git
    cd AutoClicker-Pro
    ```

2.  **Install Dependencies**
    ```bash
    pip install -r requirements.txt
    ```
    *(Dependencies: `PySide6`, `pyautogui`, `pynput`, `opencv-python`, `pillow`, `google-genai`, `packaging`)*

3.  **Run**
    ```bash
    python src/main.py
    ```

## Building Executable

To build a standalone `.exe` file yourself:

```bash
pip install pyinstaller
pyinstaller --clean AutoclickerPro.spec
```

The output will be in the `dist` folder.

## License

This project is open source and available under the [MIT License](LICENSE).
