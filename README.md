# KeepAwake

**KeepAwake** is a simple GUI tool that prevents your computer from going idle by periodically moving the mouse and pressing keys.  

It’s useful for keeping your system awake during long-running processes, presentations, or remote sessions.

---

## Features

- **Customizable interval** - Set the number of minutes between activity events.
- **Start / Stop controls** - Easily toggle the activity simulation.
- **Failsafe** - Move your mouse to the **top-left corner** of the screen to stop instantly (PyAutoGUI failsafe).
- **Safe movement** - Avoids triggering failsafe accidentally during normal operation.
- **System tray support** - Closing the window hides the app to the system tray; right-click the icon to restore or quit.
- **Log output** - Shows timestamps when activity is simulated (last 60 messages kept).
- **skip movement** - Avoid moving the mouse when the user already moved the mouse in the last interval.
---

## Requirements

- Python 3.8+
---

## Installation

1. **Clone or download** this repository.

2. Create a virtual environment:
   ```python -m venv .venv```

3. Activate the virtual environment or just jump to 4.b.:

   ```.\.venv\Scripts\activate```
4. Install dependencies:
   ```pip install pyinstaller pyautogui pillow pystray```

5. Test code before excution:
    ```& "python "./gui.py"```

6. Building the Executable
```pyinstaller.exe --onefile --windowed --name KeepAwake gui.py```
The results are available in: .\dist

---
## Usage

1. Open **KeepAwake.exe**.
2. Set the **Minutes between movements** in the text box (must be ≥ 1).
3. Click **Start** to begin.

The app will:

- Wait the set interval.
- Move the mouse slightly (avoiding the screen corner).
- Press the **Shift** key three times.
- Repeat until stopped.

4. Click **Stop** to end the process manually.
5. Or move the mouse to the **top-left corner** of the screen to trigger the failsafe stop.

---

## Notes

- This app **does not** prevent your employer’s monitoring software from logging activity; it simply simulates basic mouse/keyboard movement.
- The failsafe is **always enabled** — moving the mouse to `(0,0)` stops the process instantly.
- Built with **Python**, **Tkinter**, and **PyAutoGUI**.
