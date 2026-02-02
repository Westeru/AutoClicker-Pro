# Autoclicker Pro

A modern, feature-rich Autoclicker built with Python and CustomTkinter. Designed to be reliable, easy to use, and packed with advanced automation features.

![Autoclicker Pro](https://via.placeholder.com/800x600.png?text=Autoclicker+Pro+Interface) 
*(Screenshots can be added here)*

## Features

### 🖱️ Advanced Autoclicker
- **Precise Timing**: Set intervals in Hours, Minutes, Seconds, and Milliseconds.
- **Click Options**: Left, Right, Middle clicks. Single or Double types.
- **Key Press Mode**: Automate keyboard inputs (Press or Hold keys).
- **Modern UI**: Clean, dark-themed interface using `CustomTkinter`.

### 📼 Macro Recorder
- **Record & Replay**: Capture your mouse and keyboard actions and replay them instantly.
- **Smart Straight Lines**: Interpolate mouse movements to create perfectly straight lines during replay.
- **Repeat Counter**: Set specific repeat counts or loop infinitely.
- **Smart Stop**: Automatically excludes the "Stop" button click or Hotkey press from your recording.
- **Save/Load**: Save your complex macros to `.json` files.

### 🖼️ Image Recognition
- **Visual Automation**: Click buttons or elements based on their image.
- **Clipboard Paste**: Quickly snip a target and paste it directly into the app.
- **Grayscale Optimization**: High-performance image searching.

### ⌨️ Global Hotkeys
- **F6**: **Panic Button** (Stops everything) / Start Active Tab.
- **F7**: Toggle Recording.

## Installation (Source)

If you prefer to run from source or contribute:

1.  **Clone the repo**
    ```bash
    git clone https://github.com/yourusername/autoclicker-pro.git
    cd autoclicker-pro
    ```

2.  **Install Dependencies**
    ```bash
    pip install -r requirements.txt
    ```
    *(Dependencies: `customtkinter`, `pyautogui`, `pynput`, `opencv-python`, `pillow`, `packaging`)*

3.  **Run**
    ```bash
    python main.py
    ```

## Building Executable

To build a standalone `.exe` file:

```bash
pip install pyinstaller
pyinstaller --noconfirm --onefile --windowed --name "AutoclickerPro" --collect-all customtkinter main.py
```

The output will be in the `dist` folder.

## License

This project is open source and available under the [MIT License](LICENSE).
