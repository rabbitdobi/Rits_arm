"""Control the uHand UNO robot hand with your right hand through the camera.

Camera -> MediaPipe -> finger bend 0-180 -> Arduino over USB.
Reuses Vincent's tracker (right-hand selection, motion data, trails, drawing, CSV)
from mediapipe/VincentMediapipe without changing those files.

Run from the repository root:
    python bridge/hand_control.py --port /dev/cu.usbmodem1101
    python bridge/hand_control.py --dry-run          # test without the hand

Keys (click the preview window first):
    o : calibrate OPEN hand  (show an open hand, then press o)
    f : calibrate FIST       (make a fist, then press f)
    q / Esc : quit
"""

import argparse
from contextlib import ExitStack
import csv
from datetime import datetime
import math
from pathlib import Path
import sys
import time

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "mediapipe" / "VincentMediapipe"))
from motion import CSV_FIELDS, MotionTracker, select_right_hand, write_csv_frame  # noqa: E402

MODEL_PATH = REPO_ROOT / "mediapipe" / "models" / "hand_landmarker.task"
OUTPUT_DIR = Path(__file__).resolve().parent / "output"

FINGERS = ["Thumb", "Index", "Middle", "Ring", "Pinky"]
TIPS = [4, 8, 12, 16, 20]
WRIST, MIDDLE_BASE, PINKY_BASE = 0, 9, 17

# Default ratios (used until you calibrate). Calibration with o / f is recommended.
DEFAULT_OPEN = [1.6, 1.9, 2.0, 1.9, 1.7]
DEFAULT_FIST = [0.8, 0.9, 0.9, 0.9, 0.9]

SEND_INTERVAL = 0.05  # seconds -> 20 times per second
SMOOTHING = 0.4       # 0-1, smaller = smoother but slower

HAND_CSV_FIELDS = ["timestamp_ms", "tracked", "sent"] + [f"{name.lower()}_angle" for name in FINGERS]


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--port", help="Arduino serial port, e.g. /dev/cu.usbmodem1101 (find it with: ls /dev/cu.usb*)")
    parser.add_argument("--baud", type=int, default=115200)
    parser.add_argument("--camera", type=int, default=0, help="Camera index (default: 0)")
    parser.add_argument("--dry-run", action="store_true", help="Do not connect to the hand; only show the values")
    parser.add_argument("--no-trails", action="store_true", help="Disable glowing trails")
    args = parser.parse_args()
    if not args.dry_run and not args.port:
        parser.error("--port is required (or use --dry-run to test without the hand)")
    return args


def finger_ratios(landmarks, width, height):
    """How straight each finger is, divided by palm size so camera distance does not matter."""
    def point(i):
        return landmarks[i].x * width, landmarks[i].y * height

    def dist(a, b):
        (ax, ay), (bx, by) = point(a), point(b)
        return math.hypot(ax - bx, ay - by)

    palm = max(dist(WRIST, MIDDLE_BASE), 1e-6)
    ratios = [dist(TIPS[0], PINKY_BASE) / palm]                    # thumb: tip to pinky base
    ratios += [dist(tip, WRIST) / palm for tip in TIPS[1:]]        # others: tip to wrist
    return ratios


def to_angles(ratios, open_r, fist_r):
    """Convert ratios to 0 (fist) - 180 (open)."""
    angles = []
    for r, o, f in zip(ratios, open_r, fist_r):
        span = o - f
        value = (r - f) / span if abs(span) > 1e-6 else 1.0
        angles.append(max(0.0, min(1.0, value)) * 180)
    return angles


def open_serial(port, baud):
    import serial  # pyserial
    ser = serial.Serial(port, baud, timeout=0)
    print("Connecting to the hand (waiting 2 s for the Arduino to restart)...", file=sys.stderr)
    time.sleep(2)
    ser.reset_input_buffer()
    return ser


def draw_hand_panel(cv2, np, image, angles, calibrated, status, top):
    """Our panel, drawn below Vincent's panel."""
    height, width = image.shape[:2]
    bottom, right = min(height, top + 175), min(width, 300)
    panel = image[top:bottom, :right]
    cv2.addWeighted(panel, 0.25, np.zeros_like(panel), 0.75, 0, dst=panel)
    color = (0, 255, 0) if status in ("SENDING", "DRY RUN") else (0, 0, 255)
    cv2.putText(image, f"HAND: {status}", (12, top + 22), cv2.FONT_HERSHEY_SIMPLEX, 0.53, color, 1, cv2.LINE_AA)
    cal = f"calib  open {'OK' if calibrated['open'] else '--'}  fist {'OK' if calibrated['fist'] else '--'}"
    cv2.putText(image, cal, (12, top + 44), cv2.FONT_HERSHEY_SIMPLEX, 0.48, (220, 220, 220), 1, cv2.LINE_AA)
    if angles is not None:
        for row, (name, a) in enumerate(zip(FINGERS, angles)):
            y = top + 68 + row * 21
            cv2.putText(image, f"{name:6s} {int(a):3d}", (12, y), cv2.FONT_HERSHEY_SIMPLEX, 0.48,
                        (255, 255, 255), 1, cv2.LINE_AA)
            cv2.rectangle(image, (120, y - 10), (120 + int(a / 180 * 160), y - 2), (0, 200, 255), -1)
    cv2.putText(image, "o: open  f: fist  q: quit", (12, height - 14), cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                (200, 200, 200), 1, cv2.LINE_AA)


def run(args):
    if not MODEL_PATH.is_file():
        raise SystemExit(f"Model not found: {MODEL_PATH}")

    import cv2
    import mediapipe as mp
    import numpy as np
    from effects import FingerTrails, draw_tracking

    stamp = f"{datetime.now():%Y%m%d-%H%M%S}"
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    with ExitStack() as stack:
        ser = None if args.dry_run else open_serial(args.port, args.baud)
        if ser is not None:
            stack.callback(ser.close)

        cap = cv2.VideoCapture(args.camera)
        stack.callback(cap.release)
        if not cap.isOpened():
            raise SystemExit("Could not open the camera. Check --camera and camera permission.")

        options = mp.tasks.vision.HandLandmarkerOptions(
            base_options=mp.tasks.BaseOptions(model_asset_path=str(MODEL_PATH)),
            running_mode=mp.tasks.vision.RunningMode.VIDEO, num_hands=2,
            min_hand_detection_confidence=0.6, min_hand_presence_confidence=0.6,
            min_tracking_confidence=0.6)
        detector = stack.enter_context(mp.tasks.vision.HandLandmarker.create_from_options(options))
        stack.callback(cv2.destroyAllWindows)

        # Two recordings: Vincent's motion CSV, and the angles sent to the hand
        motion_file = stack.enter_context((OUTPUT_DIR / f"fingers-{stamp}.csv").open("x", newline="", encoding="utf-8"))
        motion_writer = csv.DictWriter(motion_file, fieldnames=CSV_FIELDS)
        motion_writer.writeheader()
        hand_file = stack.enter_context((OUTPUT_DIR / f"hand-{stamp}.csv").open("x", newline="", encoding="utf-8"))
        hand_writer = csv.DictWriter(hand_file, fieldnames=HAND_CSV_FIELDS)
        hand_writer.writeheader()
        print(f"Recording to {OUTPUT_DIR.resolve()}\nStarted. o = open hand, f = fist, q = quit", file=sys.stderr)

        tracker, trails = MotionTracker(), FingerTrails()
        open_r, fist_r = list(DEFAULT_OPEN), list(DEFAULT_FIST)
        calibrated = {"open": False, "fist": False}
        smooth = None
        start = previous_loop = last_flush = time.perf_counter()
        last_send, last_ts, fps = 0.0, -1, 0.0

        while True:
            ok, image = cap.read()
            if not ok:
                raise SystemExit("Could not read from the camera.")
            now = time.perf_counter()
            h, w = image.shape[:2]
            ts = max(last_ts + 1, int((now - start) * 1000))
            last_ts = ts

            result = detector.detect_for_video(
                mp.Image(image_format=mp.ImageFormat.SRGB, data=cv2.cvtColor(image, cv2.COLOR_BGR2RGB)), ts)
            index = select_right_hand(result)
            landmarks = None if index is None else result.hand_landmarks[index]
            score = None if index is None else max(
                c.score for c in result.handedness[index] if c.category_name == "Right")

            # Vincent's motion data and CSV
            frame = tracker.update(landmarks, ts, score)
            write_csv_frame(motion_writer, frame)

            # Our finger bend -> 0-180
            ratios = None
            if landmarks is not None:
                ratios = finger_ratios(landmarks, w, h)
                angles = to_angles(ratios, open_r, fist_r)
                smooth = angles if smooth is None else [s + SMOOTHING * (a - s) for s, a in zip(smooth, angles)]
            else:
                smooth = None  # hand lost: stop sending, the Arduino holds its position

            sent = False
            if smooth is not None and now - last_send >= SEND_INTERVAL:
                if ser is not None:
                    command = ",".join(str(int(round(a))) for a in smooth)
                    ser.write((command + "\n").encode())
                    ser.reset_input_buffer()  # ignore the Arduino's replies
                sent, last_send = True, now
            hand_writer.writerow(dict(timestamp_ms=ts, tracked=smooth is not None, sent=sent and ser is not None,
                                      **{f"{n.lower()}_angle": (round(a) if smooth else "")
                                         for n, a in zip(FINGERS, smooth or [0] * 5)}))

            if now - last_flush >= 1:
                motion_file.flush()
                hand_file.flush()
                last_flush = now

            # Preview: Vincent's trails and drawing, then our panel below his
            loop_dt = time.perf_counter() - previous_loop
            fps = 0.9 * fps + 0.1 / max(loop_dt, 1e-6) if fps else 1 / max(loop_dt, 1e-6)
            previous_loop = time.perf_counter()
            display = cv2.flip(image, 1)
            if not args.no_trails:
                trails.update(frame)
                trails.draw(display, ts)
            draw_tracking(display, landmarks, frame, fps)
            if smooth is None:
                status = "no right hand"
            else:
                status = "DRY RUN" if ser is None else "SENDING"
            draw_hand_panel(cv2, np, display, smooth, calibrated, status, top=min(h, 166) + 4)
            cv2.imshow("uHand UNO - Hand Control", display)

            key = cv2.waitKey(1) & 0xFF
            if key in (ord("q"), 27):
                break
            if key == ord("o") and ratios is not None:
                open_r, calibrated["open"] = list(ratios), True
                print("Calibrated OPEN:", [round(r, 2) for r in ratios], file=sys.stderr)
            if key == ord("f") and ratios is not None:
                fist_r, calibrated["fist"] = list(ratios), True
                print("Calibrated FIST:", [round(r, 2) for r in ratios], file=sys.stderr)

        print(f"Stopped. Recordings saved in {OUTPUT_DIR.resolve()}", file=sys.stderr)


def main():
    try:
        run(parse_args())
    except KeyboardInterrupt:
        print("Stopped.", file=sys.stderr)


if __name__ == "__main__":
    main()
