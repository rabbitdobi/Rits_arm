"""Convert Ayano's tracked hand frames to Shota's Arduino serial protocol."""

import argparse
import json
import math
from pathlib import Path
from statistics import median
import sys
import time


FINGERS = ("Thumb", "Index", "Middle", "Ring", "Pinky")
BAUD = 115200


def finger_angles(frame):
    if frame.get("tracked") is not True:
        return None
    angles = frame.get("angles")
    if not isinstance(angles, dict):
        return None
    values = tuple(angles.get(finger) for finger in FINGERS)
    if any(type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= 180
           for value in values):
        return None
    return values


def frames(stream):
    for number, line in enumerate(stream, start=1):
        if not line.strip():
            continue
        try:
            frame = json.loads(line)
        except ValueError as exc:
            raise ValueError(f"Invalid JSON on line {number}: {exc}") from exc
        if not isinstance(frame, dict):
            raise ValueError(f"Expected a frame object on line {number}")
        yield frame


def calibration_sample(path):
    with path.open(encoding="utf-8") as stream:
        samples = [angles for frame in frames(stream) if (angles := finger_angles(frame)) is not None]
    if not samples:
        raise ValueError(f"No tracked five-finger frames in {path}")
    return tuple(median(column) for column in zip(*samples[-15:]))


def calibrate(open_path, fist_path):
    opened = calibration_sample(open_path)
    closed = calibration_sample(fist_path)
    for finger, lo, hi in zip(FINGERS, opened, closed):
        if hi - lo < 5:
            raise ValueError(f"{finger}: open and fist samples differ by less than 5 degrees "
                             f"(open {lo:.1f}, fist {hi:.1f}). Capture both poses again.")
    return opened, closed


def packet(angles, opened, closed):
    values = [
        round(180 * (1 - min(1, max(0, (angle - lo) / (hi - lo)))))
        for angle, lo, hi in zip(angles, opened, closed)
    ]
    return (",".join(map(str, values)) + "\n").encode("ascii")


def send_live(stream, port, opened, closed):
    last_write = -math.inf
    for frame in frames(stream):
        angles = finger_angles(frame)
        if angles is None:
            continue
        now = time.monotonic()
        if now - last_write < 0.05:
            continue
        command = packet(angles, opened, closed)
        if port.in_waiting:
            port.read(port.in_waiting)  # Consume optional firmware echo.
        if port.write(command) != len(command):
            raise OSError("Incomplete serial write to the hand controller")
        last_write = now


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--open-sample", type=Path, required=True, help="JSONL of a held open hand")
    parser.add_argument("--fist-sample", type=Path, required=True, help="JSONL of a held fist")
    parser.add_argument("--port", help="Arduino serial device; omit for preview on stdout")
    args = parser.parse_args()
    try:
        opened, closed = calibrate(args.open_sample, args.fist_sample)
        print("Calibration (thumb, index, middle, ring, pinky):", file=sys.stderr)
        print(f"Open: {opened}\nFist: {closed}", file=sys.stderr)
        if args.port is None:
            for frame in frames(sys.stdin):
                angles = finger_angles(frame)
                if angles is not None:
                    print(packet(angles, opened, closed).decode("ascii"), end="")
            return 0
        try:
            import serial
        except ImportError:
            parser.exit(1, "Install pySerial: python3 -m pip install pyserial\n")
        with serial.Serial(args.port, BAUD, timeout=0, write_timeout=0.25, exclusive=True) as port:
            send_live(sys.stdin, port, opened, closed)
    except (ValueError, OSError) as exc:
        parser.exit(1, f"Hand bridge stopped: {exc}\n")
    except KeyboardInterrupt:
        return 130
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
