import threading
import time
from datetime import datetime
import tkinter as tk
from tkinter import ttk, messagebox
import pyautogui

pyautogui.FAILSAFE = True  # keep failsafe ON

SAFE_MARGIN = 20       # pixels away from edges to avoid (0,0) trigger # pixels away from edges to avoid failsafe
TOLERANCE_PX = 3       # ignore tiny jitter

def do_keep_awake(minutes, stop_event, log_callback, done_callback):
    minutes = max(1, int(minutes))
    interval_s = minutes * 60

    try:
        while not stop_event.is_set():
            # Record mouse position at start of interval
            start_pos = pyautogui.position()

            # Wait the whole interval (still check for stop requests)
            for _ in range(interval_s):
                if stop_event.is_set():
                    return
                time.sleep(1)

            # Get position now
            end_pos = pyautogui.position()

            # Compare positions with tolerance
            moved = abs(end_pos.x - start_pos.x) > TOLERANCE_PX or \
                    abs(end_pos.y - start_pos.y) > TOLERANCE_PX

            if not moved:
                # Perform safe movement path
                width, height = pyautogui.size()
                usable_h = max(1, height - 2 * SAFE_MARGIN)
                x = SAFE_MARGIN + 1
                steps = 50
                for i in range(steps):
                    if stop_event.is_set():
                        return
                    y = SAFE_MARGIN + (i * 4) % usable_h
                    pyautogui.moveTo(x, y)

                # Park somewhere safe and tap Shift
                pyautogui.moveTo(SAFE_MARGIN + 1, SAFE_MARGIN + 1)
                for _ in range(3):
                    if stop_event.is_set():
                        return
                    pyautogui.press("shift")

                log_callback(f"Movement made at {datetime.now().strftime('%H:%M:%S')}")
            else:
                log_callback(f"Skipped at {datetime.now().strftime('%H:%M:%S')} (mouse moved)")

    except pyautogui.FailSafeException:
        log_callback("PyAutoGUI failsafe triggered (mouse hit a corner). Stopping.")
    finally:
        done_callback()

class KeepAwakeApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Keep Awake")
        self.geometry("420x280")
        self.resizable(False, True)

        self.worker_thread = None
        self.stop_event = None

        frm = ttk.Frame(self, padding=12)
        frm.pack(fill="both", expand=True)

        self.minutes_var = tk.StringVar(value="3")

        row1 = ttk.Frame(frm)
        row1.pack(fill="x", pady=(0, 10))
        ttk.Label(row1, text="Minutes between movements:").pack(side="left")
        self.minutes_entry = ttk.Entry(row1, width=6, textvariable=self.minutes_var, justify="center")
        self.minutes_entry.pack(side="left", padx=(8, 0))

        row2 = ttk.Frame(frm)
        row2.pack(fill="x", pady=(0, 10))
        self.start_btn = ttk.Button(row2, text="Start", command=self.on_start)
        self.start_btn.pack(side="left")
        self.stop_btn = ttk.Button(row2, text="Stop", command=self.on_stop, state="disabled")
        self.stop_btn.pack(side="left", padx=8)

        ttk.Label(frm, text="Log:").pack(anchor="w")
        self.log = tk.Text(frm, height=10, state="disabled")
        self.log.pack(fill="both", expand=True)

        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def log_msg(self, msg):
        self.log.configure(state="normal")
        self.log.insert("end", msg + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def on_worker_finish(self):
        # Called on the UI thread after worker exits
        self.start_btn.configure(state="normal")
        self.minutes_entry.configure(state="normal")
        self.stop_btn.configure(state="disabled")
        self.worker_thread = None
        self.stop_event = None
        self.log_msg("Stopped.")

    def on_start(self):
        try:
            minutes = int(self.minutes_var.get().strip())
            if minutes < 1:
                raise ValueError
        except ValueError:
            messagebox.showerror("Invalid input", "Please enter a whole number of minutes (>= 1).")
            return

        if self.worker_thread and self.worker_thread.is_alive():
            return

        self.stop_event = threading.Event()
        # done_callback schedules UI cleanup safely on the main thread
        done_callback = lambda: self.after(0, self.on_worker_finish)
        self.worker_thread = threading.Thread(
            target=do_keep_awake,
            args=(minutes, self.stop_event, self.log_msg, done_callback),
            daemon=True
        )
        self.worker_thread.start()
        self.start_btn.configure(state="disabled")
        self.minutes_entry.configure(state="disabled")
        self.stop_btn.configure(state="normal")
        self.log_msg(f"Started with {minutes} minute(s) interval.")

    def on_stop(self):
        if self.stop_event:
            self.stop_event.set()

    def on_close(self):
        self.on_stop()
        # give the worker a moment to exit cleanly
        if self.worker_thread:
            self.worker_thread.join(timeout=0.5)
        self.destroy()


if __name__ == "__main__":
    app = KeepAwakeApp()
    app.mainloop()
