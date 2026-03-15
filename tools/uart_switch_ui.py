#!/usr/bin/env python3
import ctypes
import threading
import time
import tkinter as tk
from tkinter import messagebox, ttk

import serial
import serial.tools.list_ports


DEFAULT_BAUD = 115200
DEFAULT_PORT = "COM8"

BUTTONS = [
    ("A", "Z", 0, 0),
    ("B", "X", 0, 1),
    ("X", "C", 0, 2),
    ("Y", "V", 0, 3),
    ("L", "E", 1, 0),
    ("ZL", "Q", 1, 1),
    ("R", "U", 1, 2),
    ("ZR", "O", 1, 3),
    ("Minus", "-", 2, 0),
    ("Plus", "=", 2, 1),
    ("Home", "F1", 2, 2),
    ("Capture", "F2", 2, 3),
    ("L3", "R", 3, 0),
    ("R3", "P", 3, 1),
]

DPAD = [
    ("Up", "Up", 0, 1),
    ("Left", "Left", 1, 0),
    ("Right", "Right", 1, 2),
    ("Down", "Down", 2, 1),
]

LEFT_STICK = [
    ("LS Up", "W", 0, 1),
    ("LS Left", "A", 1, 0),
    ("LS Right", "D", 1, 2),
    ("LS Down", "S", 2, 1),
]

RIGHT_STICK = [
    ("RS Up", "I", 0, 1),
    ("RS Left", "J", 1, 0),
    ("RS Right", "L", 1, 2),
    ("RS Down", "K", 2, 1),
]

KEY_TO_TOKEN = {
    "z": "A",
    "x": "B",
    "c": "X",
    "v": "Y",
    "e": "L",
    "q": "ZL",
    "u": "R",
    "o": "ZR",
    "minus": "MINUS",
    "equal": "PLUS",
    "f1": "HOME",
    "f2": "CAPTURE",
    "r": "L3",
    "p": "R3",
    "up": "UP",
    "down": "DOWN",
    "left": "LEFT",
    "right": "RIGHT",
    "w": "LS_UP",
    "a": "LS_LEFT",
    "s": "LS_DOWN",
    "d": "LS_RIGHT",
    "i": "RS_UP",
    "j": "RS_LEFT",
    "k": "RS_DOWN",
    "l": "RS_RIGHT",
}

SOURCE_NOTE = (
    "Mapping base: Ryujinx keyboard defaults from source snapshots. "
    "Kept community-standard core layout: WASD left stick, IJKL right stick, "
    "Z/X/C/V face buttons, Q/E and U/O shoulders. Home/Capture and L3/R3 are local additions."
)

XINPUT_GAMEPAD_DPAD_UP = 0x0001
XINPUT_GAMEPAD_DPAD_DOWN = 0x0002
XINPUT_GAMEPAD_DPAD_LEFT = 0x0004
XINPUT_GAMEPAD_DPAD_RIGHT = 0x0008
XINPUT_GAMEPAD_START = 0x0010
XINPUT_GAMEPAD_BACK = 0x0020
XINPUT_GAMEPAD_LEFT_THUMB = 0x0040
XINPUT_GAMEPAD_RIGHT_THUMB = 0x0080
XINPUT_GAMEPAD_LEFT_SHOULDER = 0x0100
XINPUT_GAMEPAD_RIGHT_SHOULDER = 0x0200
XINPUT_GAMEPAD_A = 0x1000
XINPUT_GAMEPAD_B = 0x2000
XINPUT_GAMEPAD_X = 0x4000
XINPUT_GAMEPAD_Y = 0x8000

XINPUT_GAMEPAD_LEFT_THUMB_DEADZONE = 7849
XINPUT_GAMEPAD_RIGHT_THUMB_DEADZONE = 8689
XINPUT_GAMEPAD_TRIGGER_THRESHOLD = 30


class XInputGamepad(ctypes.Structure):
    _fields_ = [
        ("wButtons", ctypes.c_ushort),
        ("bLeftTrigger", ctypes.c_ubyte),
        ("bRightTrigger", ctypes.c_ubyte),
        ("sThumbLX", ctypes.c_short),
        ("sThumbLY", ctypes.c_short),
        ("sThumbRX", ctypes.c_short),
        ("sThumbRY", ctypes.c_short),
    ]


class XInputState(ctypes.Structure):
    _fields_ = [
        ("dwPacketNumber", ctypes.c_uint32),
        ("Gamepad", XInputGamepad),
    ]


class XInputBridge:
    def __init__(self):
        self._dll = self._load_xinput()
        self._stop_event = None
        self._thread = None
        self._active = False
        self._user_index = 0

    def _load_xinput(self):
        for name in ("xinput1_4.dll", "xinput1_3.dll", "xinput9_1_0.dll"):
            try:
                dll = ctypes.WinDLL(name)
                dll.XInputGetState.argtypes = [ctypes.c_uint32, ctypes.POINTER(XInputState)]
                dll.XInputGetState.restype = ctypes.c_uint32
                return dll
            except OSError:
                continue
        return None

    def available(self) -> bool:
        return self._dll is not None

    def get_state(self, user_index: int):
        if self._dll is None:
            return None
        state = XInputState()
        result = self._dll.XInputGetState(user_index, ctypes.byref(state))
        if result != 0:
            return None
        return state

    def start(self, user_index: int, on_tokens, on_status):
        self.stop()
        if self._dll is None:
            on_status("XInput unavailable")
            return

        self._user_index = user_index
        self._stop_event = threading.Event()

        def worker():
            last_tokens = set()
            connected = None
            while not self._stop_event.is_set():
                state = self.get_state(self._user_index)
                if state is None:
                    if connected is not False:
                        on_status(f"XInput pad {self._user_index}: disconnected")
                        connected = False
                    if last_tokens:
                        on_tokens(set())
                        last_tokens = set()
                    time.sleep(0.25)
                    continue

                if connected is not True:
                    on_status(f"XInput pad {self._user_index}: connected")
                    connected = True

                tokens = self._state_to_tokens(state)
                if tokens != last_tokens:
                    on_tokens(tokens)
                    last_tokens = tokens
                time.sleep(0.008)

        self._thread = threading.Thread(target=worker, daemon=True)
        self._thread.start()

    def stop(self):
        if self._stop_event is not None:
            self._stop_event.set()
            self._stop_event = None
        self._thread = None

    def _state_to_tokens(self, state: XInputState):
        gp = state.Gamepad
        buttons = gp.wButtons
        tokens = set()

        button_map = {
            XINPUT_GAMEPAD_A: "A",
            XINPUT_GAMEPAD_B: "B",
            XINPUT_GAMEPAD_X: "X",
            XINPUT_GAMEPAD_Y: "Y",
            XINPUT_GAMEPAD_LEFT_SHOULDER: "L",
            XINPUT_GAMEPAD_RIGHT_SHOULDER: "R",
            XINPUT_GAMEPAD_BACK: "MINUS",
            XINPUT_GAMEPAD_START: "PLUS",
            XINPUT_GAMEPAD_LEFT_THUMB: "L3",
            XINPUT_GAMEPAD_RIGHT_THUMB: "R3",
            XINPUT_GAMEPAD_DPAD_UP: "UP",
            XINPUT_GAMEPAD_DPAD_DOWN: "DOWN",
            XINPUT_GAMEPAD_DPAD_LEFT: "LEFT",
            XINPUT_GAMEPAD_DPAD_RIGHT: "RIGHT",
        }

        for mask, token in button_map.items():
            if buttons & mask:
                tokens.add(token)

        if gp.bLeftTrigger >= XINPUT_GAMEPAD_TRIGGER_THRESHOLD:
            tokens.add("ZL")
        if gp.bRightTrigger >= XINPUT_GAMEPAD_TRIGGER_THRESHOLD:
            tokens.add("ZR")

        # Standard XInput does not reliably expose the Guide button in XInputGetState.
        # Use Back+Start as a practical HOME fallback for remote play.
        if (buttons & XINPUT_GAMEPAD_BACK) and (buttons & XINPUT_GAMEPAD_START):
            tokens.add("HOME")

        left_x, left_y = gp.sThumbLX, gp.sThumbLY
        right_x, right_y = gp.sThumbRX, gp.sThumbRY

        if left_y >= XINPUT_GAMEPAD_LEFT_THUMB_DEADZONE:
            tokens.add("LS_UP")
        elif left_y <= -XINPUT_GAMEPAD_LEFT_THUMB_DEADZONE:
            tokens.add("LS_DOWN")
        if left_x >= XINPUT_GAMEPAD_LEFT_THUMB_DEADZONE:
            tokens.add("LS_RIGHT")
        elif left_x <= -XINPUT_GAMEPAD_LEFT_THUMB_DEADZONE:
            tokens.add("LS_LEFT")

        if right_y >= XINPUT_GAMEPAD_RIGHT_THUMB_DEADZONE:
            tokens.add("RS_UP")
        elif right_y <= -XINPUT_GAMEPAD_RIGHT_THUMB_DEADZONE:
            tokens.add("RS_DOWN")
        if right_x >= XINPUT_GAMEPAD_RIGHT_THUMB_DEADZONE:
            tokens.add("RS_RIGHT")
        elif right_x <= -XINPUT_GAMEPAD_RIGHT_THUMB_DEADZONE:
            tokens.add("RS_LEFT")

        return tokens


def normalize_keysym(keysym: str) -> str:
    return keysym.lower() if len(keysym) > 1 else keysym


class SerialBridge:
    def __init__(self):
        self._ser = None
        self._lock = threading.Lock()
        self._reader_stop = None

    def connect(self, port: str, baud: int):
        self.disconnect()
        with self._lock:
            self._ser = serial.Serial(port, baud, timeout=0.05)
            time.sleep(0.2)

    def disconnect(self):
        with self._lock:
            if self._reader_stop is not None:
                self._reader_stop.set()
                self._reader_stop = None
            if self._ser is not None:
                try:
                    self._ser.close()
                finally:
                    self._ser = None

    def is_connected(self) -> bool:
        return self._ser is not None and self._ser.is_open

    def send_line(self, line: str):
        with self._lock:
            if not self.is_connected():
                raise RuntimeError("Serial port is not connected.")
            self._ser.write((line + "\n").encode("ascii"))

    def start_reader(self, on_line):
        stop_event = threading.Event()
        self._reader_stop = stop_event

        def worker():
            while not stop_event.is_set():
                try:
                    with self._lock:
                        ser = self._ser
                    if ser is None or not ser.is_open:
                        time.sleep(0.05)
                        continue
                    raw = ser.readline()
                    if raw:
                        on_line(raw.decode("ascii", errors="replace").strip())
                except Exception as exc:
                    on_line(f"[read error] {exc}")
                    time.sleep(0.2)

        threading.Thread(target=worker, daemon=True).start()


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("GP2040 UART Switch UI")
        self.geometry("980x760")
        self.minsize(940, 700)

        self.bridge = SerialBridge()
        self.xinput = XInputBridge()
        self.status_var = tk.StringVar(value="Disconnected")
        self.port_var = tk.StringVar(value=DEFAULT_PORT)
        self.baud_var = tk.StringVar(value=str(DEFAULT_BAUD))
        self.mode_var = tk.StringVar(value="hold")
        self.log_var = tk.StringVar(value="Ready")
        self.xinput_enabled_var = tk.BooleanVar(value=True)
        self.xinput_index_var = tk.StringVar(value="0")
        self.xinput_status_var = tk.StringVar(
            value="XInput unavailable" if not self.xinput.available() else "XInput idle"
        )
        self._connecting = False
        self._pressed_keys = set()
        self._token_sources = {}
        self._xinput_tokens = set()

        self._build_ui()
        self._bind_keys()
        self.refresh_ports()
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def _build_ui(self):
        root = ttk.Frame(self, padding=12)
        root.pack(fill="both", expand=True)

        conn = ttk.LabelFrame(root, text="Connection", padding=10)
        conn.pack(fill="x")

        ttk.Label(conn, text="Port").grid(row=0, column=0, sticky="w")
        self.port_combo = ttk.Combobox(conn, textvariable=self.port_var, width=18)
        self.port_combo.grid(row=0, column=1, padx=6, sticky="w")

        ttk.Label(conn, text="Baud").grid(row=0, column=2, sticky="w")
        ttk.Entry(conn, textvariable=self.baud_var, width=10).grid(row=0, column=3, padx=6, sticky="w")

        ttk.Button(conn, text="Refresh", command=self.refresh_ports).grid(row=0, column=4, padx=6)
        self.connect_button = ttk.Button(conn, text="Connect", command=self.connect)
        self.connect_button.grid(row=0, column=5, padx=6)
        ttk.Button(conn, text="Disconnect", command=self.disconnect).grid(row=0, column=6, padx=6)
        ttk.Label(conn, textvariable=self.status_var).grid(row=0, column=7, padx=12, sticky="w")

        mode = ttk.LabelFrame(root, text="Send Mode", padding=10)
        mode.pack(fill="x", pady=10)
        ttk.Radiobutton(mode, text="Hold (key down/up passthrough)", variable=self.mode_var, value="hold").pack(side="left")
        ttk.Radiobutton(mode, text="Tap", variable=self.mode_var, value="tap").pack(side="left", padx=12)
        ttk.Button(mode, text="Release All", command=self.release_all).pack(side="right")

        xinput = ttk.LabelFrame(root, text="XInput", padding=10)
        xinput.pack(fill="x", pady=(0, 10))
        ttk.Checkbutton(
            xinput,
            text="Enable XInput bridge",
            variable=self.xinput_enabled_var,
            command=self._refresh_xinput_bridge,
        ).grid(row=0, column=0, sticky="w")
        ttk.Label(xinput, text="Pad").grid(row=0, column=1, padx=(12, 4), sticky="w")
        ttk.Combobox(
            xinput,
            textvariable=self.xinput_index_var,
            values=["0", "1", "2", "3"],
            width=4,
            state="readonly",
        ).grid(row=0, column=2, sticky="w")
        ttk.Button(xinput, text="Apply", command=self._refresh_xinput_bridge).grid(row=0, column=3, padx=8)
        ttk.Label(xinput, textvariable=self.xinput_status_var).grid(row=0, column=4, padx=12, sticky="w")

        top = ttk.Frame(root)
        top.pack(fill="both", expand=True)

        dpad_frame = ttk.LabelFrame(top, text="D-Pad", padding=10)
        dpad_frame.pack(side="left", fill="both", expand=True, padx=(0, 6))
        self._build_token_grid(dpad_frame, DPAD)

        face_frame = ttk.LabelFrame(top, text="Buttons", padding=10)
        face_frame.pack(side="left", fill="both", expand=True, padx=6)
        self._build_token_grid(face_frame, BUTTONS)

        left_stick_frame = ttk.LabelFrame(top, text="Left Stick", padding=10)
        left_stick_frame.pack(side="left", fill="both", expand=True, padx=6)
        self._build_token_grid(left_stick_frame, LEFT_STICK)

        right_stick_frame = ttk.LabelFrame(top, text="Right Stick", padding=10)
        right_stick_frame.pack(side="left", fill="both", expand=True, padx=(6, 0))
        self._build_token_grid(right_stick_frame, RIGHT_STICK)

        info = ttk.LabelFrame(root, text="Keyboard Mapping", padding=10)
        info.pack(fill="x", pady=(10, 0))
        mapping_text = (
            "Left stick: W/A/S/D   Right stick: I/J/K/L   D-pad: Arrow keys   "
            "A/B/X/Y: Z/X/C/V   ZL/L: Q/E   R/ZR: U/O   Minus/Plus: -/=   "
            "L3/R3: R/P   Home/Capture: F1/F2"
        )
        ttk.Label(info, text=mapping_text, wraplength=920, justify="left").pack(anchor="w")
        ttk.Label(info, text=SOURCE_NOTE, wraplength=920, justify="left", foreground="#555").pack(anchor="w", pady=(6, 0))
        ttk.Label(
            info,
            text=(
                "XInput bridge: Xbox A/B/X/Y -> Switch A/B/X/Y, LB/RB -> L/R, LT/RT -> ZL/ZR, "
                "Back/Start -> Minus/Plus, sticks/dpad passthrough, Home -> Back+Start fallback."
            ),
            wraplength=920,
            justify="left",
            foreground="#555",
        ).pack(anchor="w", pady=(6, 0))

        state = ttk.LabelFrame(root, text="Status", padding=10)
        state.pack(fill="x", pady=(10, 0))
        ttk.Label(state, textvariable=self.log_var).pack(anchor="w")

        logs = ttk.Frame(root)
        logs.pack(fill="both", expand=True, pady=(10, 0))

        tx = ttk.LabelFrame(logs, text="TX", padding=10)
        tx.pack(side="left", fill="both", expand=True, padx=(0, 6))
        self.tx_text = tk.Text(tx, height=12, wrap="word", state="disabled")
        self.tx_text.pack(fill="both", expand=True)

        rx = ttk.LabelFrame(logs, text="RX", padding=10)
        rx.pack(side="left", fill="both", expand=True, padx=(6, 0))
        self.rx_text = tk.Text(rx, height=12, wrap="word", state="disabled")
        self.rx_text.pack(fill="both", expand=True)

    def _build_token_grid(self, parent, layout):
        for label, key_hint, row, col in layout:
            token = label.upper().replace(" ", "_")
            btn = ttk.Button(parent, text=f"{label}\n[{key_hint}]", width=10)
            btn.grid(row=row, column=col, padx=6, pady=6, sticky="nsew")
            btn.bind("<ButtonPress-1>", lambda event, t=token: self.on_token_press(t))
            btn.bind("<ButtonRelease-1>", lambda event, t=token: self.on_token_release(t))
        for index in range(4):
            parent.grid_columnconfigure(index, weight=1)
            parent.grid_rowconfigure(index, weight=1)

    def _bind_keys(self):
        self.bind_all("<KeyPress>", self._handle_key_press)
        self.bind_all("<KeyRelease>", self._handle_key_release)

    def refresh_ports(self):
        ports = [p.device for p in serial.tools.list_ports.comports()]
        self.port_combo["values"] = ports
        if ports and self.port_var.get() not in ports:
            self.port_var.set(ports[0])
        self.log_var.set("No serial ports found" if not ports else f"Ports: {', '.join(ports)}")

    def connect(self):
        if self._connecting:
            return

        port = self.port_var.get().strip()
        if not port:
            messagebox.showerror("Connect failed", "Port is empty.")
            return

        try:
            baud = int(self.baud_var.get().strip())
        except ValueError:
            messagebox.showerror("Connect failed", "Baud must be a number.")
            return

        self._connecting = True
        self.connect_button.state(["disabled"])
        self.status_var.set(f"Connecting: {port}")
        self.log_var.set(f"Connecting to {port} @ {baud}")

        def worker():
            try:
                self.bridge.connect(port, baud)
            except Exception as exc:
                self.after(0, lambda: self._on_connect_failed(str(exc)))
                return
            self.after(0, lambda: self._on_connect_success(port))

        threading.Thread(target=worker, daemon=True).start()

    def _on_connect_success(self, port: str):
        self._connecting = False
        self.connect_button.state(["!disabled"])
        self.status_var.set(f"Connected: {port}")
        self.log_var.set("Connected")
        self.bridge.start_reader(lambda line: self.after(0, self.append_rx, line))
        self.append_rx(f"[connected] {port}")
        self._refresh_xinput_bridge()
        self.focus_force()

    def _on_connect_failed(self, error: str):
        self._connecting = False
        self.connect_button.state(["!disabled"])
        self.status_var.set("Disconnected")
        self.log_var.set(f"Connect failed: {error}")
        messagebox.showerror("Connect failed", error)

    def disconnect(self):
        self.release_all(log_only=True)
        self.xinput.stop()
        self._apply_xinput_tokens(set())
        self.xinput_status_var.set("XInput idle" if self.xinput.available() else "XInput unavailable")
        self.bridge.disconnect()
        self.status_var.set("Disconnected")
        self.log_var.set("Disconnected")
        self.append_rx("[disconnected]")

    def send_line(self, line: str):
        try:
            self.bridge.send_line(line)
            self.log_var.set(f"Sent: {line}")
            self.append_tx(line)
        except Exception as exc:
            self.log_var.set(f"Send failed: {exc}")

    def _activate_token(self, source: str, token: str):
        holders = self._token_sources.setdefault(token, set())
        if source in holders:
            return
        should_send = not holders
        holders.add(source)
        if should_send:
            self.send_line(f"P:{token}")

    def _deactivate_token(self, source: str, token: str):
        holders = self._token_sources.get(token)
        if not holders or source not in holders:
            return
        holders.discard(source)
        if holders:
            return
        self._token_sources.pop(token, None)
        self.send_line(f"R:{token}")

    def release_all(self, log_only: bool = False):
        self._pressed_keys.clear()
        self._xinput_tokens.clear()
        self._token_sources.clear()
        if log_only:
            self.append_tx("C")
            return
        self.send_line("C")

    def tap_token(self, token: str, hold: float = 0.08):
        def worker():
            self.send_line(f"P:{token}")
            time.sleep(hold)
            self.send_line(f"R:{token}")

        threading.Thread(target=worker, daemon=True).start()

    def on_token_press(self, token: str):
        if self.mode_var.get() == "tap":
            self.tap_token(token)
        else:
            self._activate_token(f"mouse:{token}", token)

    def on_token_release(self, token: str):
        if self.mode_var.get() == "hold":
            self._deactivate_token(f"mouse:{token}", token)

    def _handle_key_press(self, event):
        key = normalize_keysym(event.keysym)
        token = KEY_TO_TOKEN.get(key)
        if token is None:
            return
        if key in self._pressed_keys and self.mode_var.get() == "hold":
            return
        self._pressed_keys.add(key)
        if self.mode_var.get() == "tap":
            self.tap_token(token)
        else:
            self._activate_token(f"key:{key}", token)

    def _handle_key_release(self, event):
        key = normalize_keysym(event.keysym)
        token = KEY_TO_TOKEN.get(key)
        if token is None:
            return
        self._pressed_keys.discard(key)
        if self.mode_var.get() == "hold":
            self._deactivate_token(f"key:{key}", token)

    def _refresh_xinput_bridge(self):
        self.xinput.stop()
        self._apply_xinput_tokens(set())

        if not self.bridge.is_connected():
            self.xinput_status_var.set("XInput waiting for serial connect")
            return

        if not self.xinput_enabled_var.get():
            self.xinput_status_var.set("XInput disabled")
            return

        try:
            pad_index = int(self.xinput_index_var.get())
        except ValueError:
            self.xinput_status_var.set("XInput pad index invalid")
            return

        self.xinput.start(
            pad_index,
            lambda tokens: self.after(0, self._apply_xinput_tokens, tokens),
            lambda status: self.after(0, self.xinput_status_var.set, status),
        )

    def _apply_xinput_tokens(self, tokens):
        tokens = set(tokens)
        source = "xinput"
        for token in sorted(self._xinput_tokens - tokens):
            self._deactivate_token(source, token)
        for token in sorted(tokens - self._xinput_tokens):
            self._activate_token(source, token)
        self._xinput_tokens = tokens

    def append_tx(self, line: str):
        self._append_log(self.tx_text, line)

    def append_rx(self, line: str):
        self._append_log(self.rx_text, line)

    def _append_log(self, widget: tk.Text, line: str):
        widget.configure(state="normal")
        widget.insert("end", line + "\n")
        widget.see("end")
        widget.configure(state="disabled")

    def on_close(self):
        self.disconnect()
        self.destroy()


if __name__ == "__main__":
    App().mainloop()
