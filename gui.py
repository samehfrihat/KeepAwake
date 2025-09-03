import threading
import time
from datetime import datetime
import tkinter as tk
from tkinter import ttk, messagebox
import pyautogui
import pystray
from PIL import Image, ImageDraw

pyautogui.FAILSAFE = True  # keep failsafe ON

SAFE_MARGIN = 20       # pixels away from edges to avoid (0,0) trigger # pixels away from edges to avoid failsafe
TOLERANCE_PX = 3       # ignore tiny jitter
MAX_LOG_LINES = 60     # store up to 60 log messages


def create_tray_image():
    img = Image.new("RGB", (64, 64), "black")
    d = ImageDraw.Draw(img)
    d.rectangle((16, 16, 48, 48), fill="white")
    return img

def do_keep_awake(minutes, stop_event, log_callback, done_callback):
    minutes = max(1, int(minutes))
    interval_s = minutes * 60

    MAX_RETRIES = 3
    FAILSAFE_RECOVERIES = 3
    retries = 0

    while not stop_event.is_set() and retries <= MAX_RETRIES:
        try:
            while not stop_event.is_set():
                # Record mouse position at start of interval
                start_pos = pyautogui.position()

                # Wait the whole interval (still check for stop requests)
                for _ in range(interval_s):
                    if stop_event.is_set():
                        done_callback()
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
                    failsafe_hits = 0
                    interrupted = False
                    for i in range(steps):
                        if stop_event.is_set():
                            done_callback()
                            return
                        y = SAFE_MARGIN + (i * 4) % usable_h
                        target = (x, y)
                        try:
                            pyautogui.moveTo(*target)
                            actual = pyautogui.position()
                            if abs(actual.x - target[0]) > TOLERANCE_PX or \
                               abs(actual.y - target[1]) > TOLERANCE_PX:
                                log_callback("Movement cancelled - user took control.")
                                interrupted = True
                                break
                        except pyautogui.FailSafeException:
                            pos = pyautogui.position()
                            log_callback(
                                f"Failsafe at ({pos.x},{pos.y}) {datetime.now().strftime('%H:%M:%S')} - attempting recovery"
                            )
                            failsafe_hits += 1
                            try:
                                pyautogui.moveTo(SAFE_MARGIN + 1, SAFE_MARGIN + 1)
                            except pyautogui.FailSafeException:
                                failsafe_hits += 1
                            if failsafe_hits >= FAILSAFE_RECOVERIES:
                                raise
                            continue

                    if not interrupted:
                        try:
                            pyautogui.moveTo(SAFE_MARGIN + 1, SAFE_MARGIN + 1)
                        except pyautogui.FailSafeException:
                            pos = pyautogui.position()
                            log_callback(
                                f"Failsafe at ({pos.x},{pos.y}) {datetime.now().strftime('%H:%M:%S')} during parking - attempting recovery"
                            )
                            failsafe_hits += 1
                            try:
                                pyautogui.moveTo(SAFE_MARGIN + 1, SAFE_MARGIN + 1)
                            except pyautogui.FailSafeException:
                                failsafe_hits += 1
                            if failsafe_hits >= FAILSAFE_RECOVERIES:
                                raise
                        for _ in range(3):
                            if stop_event.is_set():
                                done_callback()
                                return
                            pyautogui.press("shift")

                        log_callback(f"Movement made at {datetime.now().strftime('%H:%M:%S')}")
                else:
                    log_callback(f"Skipped at {datetime.now().strftime('%H:%M:%S')} (mouse moved)")

            done_callback()
            return
        except pyautogui.FailSafeException:
            if stop_event.is_set():
                break
            retries += 1
            if retries <= MAX_RETRIES:
                log_callback(
                    f"PyAutoGUI failsafe triggered - retrying ({retries}/{MAX_RETRIES})"
                )
                time.sleep(1)
            else:
                log_callback("PyAutoGUI failsafe triggered repeatedly - giving up.")
        except Exception as e:
            if stop_event.is_set():
                break
            retries += 1
            if retries <= MAX_RETRIES:
                log_callback(
                    f"Worker stopped unexpectedly ({e}). Retrying ({retries}/{MAX_RETRIES})"
                )
                time.sleep(1)
            else:
                log_callback(f"Worker stopped unexpectedly ({e}). Giving up.")

    done_callback()

class KeepAwakeApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Keep Awake")
        self.geometry("420x280")
        self.resizable(False, True)

        self.worker_thread = None
        self.stop_event = None
        self.tray_icon = None

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
        lines = int(self.log.index('end-1c').split('.')[0])
        if lines > MAX_LOG_LINES:
            self.log.delete('1.0', f"{lines - MAX_LOG_LINES + 1}.0")
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
        self.withdraw()
        self.show_tray_icon()

    def show_tray_icon(self):
        if self.tray_icon:
            return
        image = create_tray_image()
        menu = pystray.Menu(
            pystray.MenuItem("Show", lambda icon, item: self.show_window()),
            pystray.MenuItem("Quit", lambda icon, item: self.quit_from_tray())
        )
        self.tray_icon = pystray.Icon("keepawake", image, "KeepAwake", menu)
        self.tray_icon.run_detached()

    def show_window(self):
        self.after(0, self._show_window)

    def _show_window(self):
        if self.tray_icon:
            self.tray_icon.stop()
            self.tray_icon = None
        self.deiconify()
        self.lift()

    def quit_from_tray(self):
        self.after(0, self._quit_app)

    def _quit_app(self):
        self.on_stop()
        if self.worker_thread:
            self.worker_thread.join(timeout=0.5)
        if self.tray_icon:
            self.tray_icon.stop()
            self.tray_icon = None
        self.destroy()


if __name__ == "__main__":
    app = KeepAwakeApp()
    app.mainloop()
