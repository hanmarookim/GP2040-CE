#!/usr/bin/env python3
"""
Raw HID logger for Nintendo Pro Controllers on PC.

Usage:
    pip install hidapi
    python procon_home_logger.py --list
    python procon_home_logger.py --pid 0x2009

Notes:
    - Official Nintendo Switch Pro Controller over USB is commonly VID 0x057E / PID 0x2009.
    - If you are testing a newer Nintendo controller, first use --list and check the PID that
      Windows exposes on your machine.
    - Steam / BetterJoy / DS4Windows / other input wrappers can grab the device and prevent
      raw HID reads from matching what you expect.
"""

from __future__ import annotations

import argparse
import csv
import time
from pathlib import Path
from typing import Iterable

import hid


NINTENDO_VID = 0x057E
DEFAULT_PIDS = (
    0x2009,  # Switch Pro Controller (common USB PID)
    0x2066,
    0x2067,
    0x2069,
    0x2073,
)


def hex_bytes(data: Iterable[int]) -> str:
    return " ".join(f"{b:02X}" for b in data)


def list_devices() -> list[dict]:
    devices = [d for d in hid.enumerate() if d["vendor_id"] == NINTENDO_VID]
    if not devices:
        print("No Nintendo HID devices found.")
        return []

    for idx, dev in enumerate(devices):
        print(
            f"[{idx}] "
            f"VID=0x{dev['vendor_id']:04X} "
            f"PID=0x{dev['product_id']:04X} "
            f'product="{dev.get("product_string") or ""}" '
            f'path="{dev.get("path")}"'
        )
    return devices


def decode_buttons_30(report: list[int]) -> tuple[list[str], tuple[int, int, int]] | tuple[None, None]:
    if len(report) < 13 or report[0] != 0x30:
        return None, None

    b0, b1, b2 = report[3], report[4], report[5]
    flags = []

    if b0 & 0x01:
        flags.append("B")
    if b0 & 0x02:
        flags.append("A")
    if b0 & 0x04:
        flags.append("Y")
    if b0 & 0x08:
        flags.append("X")
    if b0 & 0x10:
        flags.append("R")
    if b0 & 0x20:
        flags.append("ZR")
    if b0 & 0x40:
        flags.append("PLUS")
    if b0 & 0x80:
        flags.append("R3")

    if b1 & 0x01:
        flags.append("DOWN")
    if b1 & 0x02:
        flags.append("RIGHT")
    if b1 & 0x04:
        flags.append("LEFT")
    if b1 & 0x08:
        flags.append("UP")
    if b1 & 0x10:
        flags.append("L")
    if b1 & 0x20:
        flags.append("ZL")
    if b1 & 0x40:
        flags.append("MINUS")
    if b1 & 0x80:
        flags.append("L3")

    if b2 & 0x01:
        flags.append("HOME")
    if b2 & 0x02:
        flags.append("CAPTURE")

    return flags, (b0, b1, b2)


def extract_candidate_button_bytes(report: list[int]) -> tuple[int, tuple[int, int, int]] | None:
    if len(report) >= 6 and report[0] == 0x30:
        return report[0], (report[3], report[4], report[5])

    # Some Windows/Bluetooth paths surface a different report id while still carrying
    # a 3-byte button block near the front. Keep this heuristic separate from the
    # official 0x30 decoder so we can still watch for stable button-byte changes.
    if len(report) >= 11 and report[0] in {0x21, 0x31, 0x3F, 0x05}:
        return report[0], (report[3], report[4], report[5])

    return None


def decode_report(report: list[int]) -> str:
    flags, raw_btn = decode_buttons_30(report)
    if flags is not None and raw_btn is not None:
        b0, b1, b2 = raw_btn
        return (
            f"id=0x30 buttons=[{', '.join(flags) if flags else 'none'}] "
            f"raw_btn={b0:02X} {b1:02X} {b2:02X}"
        )

    if len(report) < 1:
        return "short-report"
    return f"id=0x{report[0]:02X} raw={hex_bytes(report[:16])}"


def diff_buttons(previous: set[str], current: set[str]) -> tuple[list[str], list[str]]:
    pressed = sorted(current - previous)
    released = sorted(previous - current)
    return pressed, released


def open_device(pid: int | None, path: bytes | None) -> hid.device:
    dev = hid.device()
    if path:
        dev.open_path(path)
    elif pid is not None:
        dev.open(NINTENDO_VID, pid)
    else:
        raise ValueError("Either pid or path must be provided")
    dev.set_nonblocking(False)
    return dev


def capture_window(
    dev: hid.device,
    timeout_ms: int,
    duration_ms: int,
) -> list[list[int]]:
    deadline = time.monotonic() + (duration_ms / 1000.0)
    frames: list[list[int]] = []
    while time.monotonic() < deadline:
        report = dev.read(64, timeout_ms=timeout_ms)
        if report:
            frames.append(report)
    return frames


def save_capture_csv(path: Path, label: str, frames: list[list[int]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["label", "frame_index", "report_id", "report_hex"])
        for index, frame in enumerate(frames):
            report_id = f"0x{frame[0]:02X}" if frame else ""
            writer.writerow([label, index, report_id, hex_bytes(frame)])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--list", action="store_true", help="List Nintendo HID devices and exit")
    parser.add_argument("--pid", type=lambda x: int(x, 0), help="Open by product id, e.g. 0x2009")
    parser.add_argument("--index", type=int, help="Open the indexed device from --list output")
    parser.add_argument("--all", action="store_true", help="Print all reports, not only changes")
    parser.add_argument("--home-only", action="store_true", help="Only print and save HOME button transitions")
    parser.add_argument(
        "--button-bytes-only",
        action="store_true",
        help="Ignore packet-wide changes and only react to button-byte changes",
    )
    parser.add_argument(
        "--save",
        type=Path,
        help="Save filtered button transitions to a CSV file",
    )
    parser.add_argument(
        "--capture-label",
        help="Interactive single-button capture label, e.g. HOME",
    )
    parser.add_argument(
        "--capture-ms",
        type=int,
        default=500,
        help="Capture duration in ms for --capture-label mode",
    )
    parser.add_argument(
        "--capture-out",
        type=Path,
        help="Output CSV path for --capture-label mode",
    )
    parser.add_argument("--timeout-ms", type=int, default=500, help="Read timeout in ms")
    args = parser.parse_args()

    devices = list_devices()
    if args.list:
        return 0

    chosen_path = None
    chosen_pid = args.pid

    if args.index is not None:
        if args.index < 0 or args.index >= len(devices):
            print("Invalid --index")
            return 1
        chosen_path = devices[args.index]["path"]
        chosen_pid = devices[args.index]["product_id"]
    elif chosen_pid is None:
        for candidate in DEFAULT_PIDS:
            if any(d["product_id"] == candidate for d in devices):
                chosen_pid = candidate
                break

    if chosen_pid is None and chosen_path is None:
        print("No matching Nintendo controller found. Use --list first.")
        return 1

    print(
        f"Opening device: VID=0x{NINTENDO_VID:04X} "
        f"PID=0x{chosen_pid:04X}" if chosen_pid is not None else "Opening indexed device"
    )

    try:
        dev = open_device(chosen_pid, chosen_path)
    except OSError as exc:
        print(f"Failed to open HID device: {exc}")
        print("Close Steam, BetterJoy, DS4Windows, or any app that may own the controller.")
        return 1

    if args.capture_label:
        output_path = args.capture_out or Path(f"capture_{args.capture_label.lower()}.csv")
        print(f"Capture label: {args.capture_label}")
        print(f"Output: {output_path}")
        print("When ready, press Enter and immediately press the target button once.")
        input()
        frames = capture_window(dev, args.timeout_ms, args.capture_ms)
        save_capture_csv(output_path, args.capture_label, frames)
        dev.close()
        print(f"Saved {len(frames)} frame(s) to {output_path}")
        return 0

    log_writer = None
    log_file = None
    if args.save:
        log_file = args.save.open("w", newline="", encoding="utf-8")
        log_writer = csv.writer(log_file)
        log_writer.writerow(["timestamp", "event", "buttons", "raw_b0", "raw_b1", "raw_b2"])

    last_report = None
    last_home = None
    last_buttons: set[str] = set()
    last_button_bytes = None

    print("Reading reports. Press Ctrl+C to stop.")
    try:
        while True:
            report = dev.read(64, timeout_ms=args.timeout_ms)
            if not report:
                continue

            flags, raw_btn = decode_buttons_30(report)
            current_buttons = set(flags or [])
            current_home = "HOME" in current_buttons if flags is not None else None
            candidate_button_bytes = extract_candidate_button_bytes(report)

            changed = report != last_report
            button_bytes_changed = candidate_button_bytes != last_button_bytes
            if flags is not None:
                pressed, released = diff_buttons(last_buttons, current_buttons)
                interesting = pressed or released
                if args.home_only:
                    pressed = [b for b in pressed if b == "HOME"]
                    released = [b for b in released if b == "HOME"]
                    interesting = pressed or released

                if args.all or interesting:
                    stamp = time.strftime("%Y-%m-%d %H:%M:%S")
                    summary = []
                    if pressed:
                        summary.append(f"PRESS {','.join(pressed)}")
                    if released:
                        summary.append(f"RELEASE {','.join(released)}")
                    message = " | ".join(summary) if summary else decode_report(report)
                    print(f"[{stamp}] {message}")

                    if log_writer and raw_btn is not None:
                        b0, b1, b2 = raw_btn
                        for name in pressed:
                            log_writer.writerow([stamp, f"PRESS:{name}", ",".join(sorted(current_buttons)), f"{b0:02X}", f"{b1:02X}", f"{b2:02X}"])
                        for name in released:
                            log_writer.writerow([stamp, f"RELEASE:{name}", ",".join(sorted(current_buttons)), f"{b0:02X}", f"{b1:02X}", f"{b2:02X}"])
                        log_file.flush()
            elif candidate_button_bytes is not None and (args.all or button_bytes_changed):
                stamp = time.strftime("%Y-%m-%d %H:%M:%S")
                report_id, (b0, b1, b2) = candidate_button_bytes
                if not args.button_bytes_only:
                    print(f"[{stamp}] id=0x{report_id:02X} button_bytes={b0:02X} {b1:02X} {b2:02X}")
                if log_writer:
                    log_writer.writerow([stamp, f"BUTTON_BYTES:0x{report_id:02X}", "", f"{b0:02X}", f"{b1:02X}", f"{b2:02X}"])
                    log_file.flush()
            elif (not args.button_bytes_only) and (args.all or changed):
                stamp = time.strftime("%Y-%m-%d %H:%M:%S")
                print(f"[{stamp}] {decode_report(report)}")

            last_report = report
            last_home = current_home
            last_buttons = current_buttons
            last_button_bytes = candidate_button_bytes
    except KeyboardInterrupt:
        pass
    finally:
        dev.close()
        if log_file:
            log_file.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
