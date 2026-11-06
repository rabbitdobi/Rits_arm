"""Track right-hand fingertip motion. Run with --help for recording options."""

import argparse
from contextlib import ExitStack
import csv
from datetime import datetime
import json
import math
from pathlib import Path
import sys
import time

from motion import CSV_FIELDS, MotionTracker, select_right_hand, write_csv_frame

SCRIPT_DIR = Path(__file__).resolve().parent


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--camera", type=int, default=0, help="Camera index (default: 0)")
    source.add_argument("--video", type=Path, help="Read a constant-frame-rate video instead")
    parser.add_argument("--model", type=Path, default=SCRIPT_DIR / "hand_landmarker.task")
    parser.add_argument("--csv", type=Path, help="New CSV path (default: output/fingers-TIMESTAMP.csv)")
    parser.add_argument("--json", action="store_true", help="Emit one JSON object per frame on stdout")
    parser.add_argument("--headless", action="store_true", help="Disable the preview window")
    parser.add_argument("--no-trails", action="store_true", help="Disable glowing trails")
    return parser.parse_args(argv)


def run(args):
    output = args.csv or (SCRIPT_DIR.parent / "output" /
                          f"fingers-{datetime.now():%Y%m%d-%H%M%S-%f}.csv")
    if output.exists():
        raise SystemExit(f"Recording already exists: {output}. Choose a new --csv path.")
    if not args.model.is_file():
        raise SystemExit(f"Model file not found: {args.model}. See mediapipe/README.md.")
    if args.video is not None and not args.video.is_file():
        raise SystemExit(f"Video file not found: {args.video}")

    # Keep --help available before optional vision packages are installed.
    import cv2
    import mediapipe as mp
    from effects import FingerTrails, draw_tracking

    with ExitStack() as stack:
        cap = cv2.VideoCapture(str(args.video) if args.video is not None else args.camera)
        stack.callback(cap.release)
        if not cap.isOpened():
            raise SystemExit("Could not open video/camera. Check --camera and camera permissions.")
        video_fps = cap.get(cv2.CAP_PROP_FPS) if args.video is not None else None
        if video_fps is not None and (not math.isfinite(video_fps) or video_fps <= 0):
            raise SystemExit("Video has no valid frame rate; use a constant-frame-rate video.")
        options = mp.tasks.vision.HandLandmarkerOptions(
            base_options=mp.tasks.BaseOptions(model_asset_path=str(args.model)),
            running_mode=mp.tasks.vision.RunningMode.VIDEO, num_hands=2,
            min_hand_detection_confidence=0.6, min_hand_presence_confidence=0.6,
            min_tracking_confidence=0.6)
        detector = stack.enter_context(mp.tasks.vision.HandLandmarker.create_from_options(options))
        if not args.headless:
            stack.callback(cv2.destroyAllWindows)
        output.parent.mkdir(parents=True, exist_ok=True)
        recording = stack.enter_context(output.open("x", newline="", encoding="utf-8"))
        writer = csv.DictWriter(recording, fieldnames=CSV_FIELDS)
        writer.writeheader()
        print(f"Recording: {output.resolve()}\nPress q / Esc or Ctrl-C to stop.", file=sys.stderr)
        tracker, trails = MotionTracker(), FingerTrails()
        start = previous_loop = time.perf_counter()
        last_flush = start
        frame_index, last_timestamp, fps = 0, -1, 0.0

        while True:
            success, image = cap.read()
            now = time.perf_counter()
            if not success:
                if args.video is None or frame_index == 0:
                    raise SystemExit("Could not read a frame from video/camera.")
                break
            elapsed_ms = (frame_index * 1000 / video_fps if video_fps is not None
                          else (now - start) * 1000)
            timestamp_ms = max(last_timestamp + 1, int(elapsed_ms))
            last_timestamp = timestamp_ms
            result = detector.detect_for_video(
                mp.Image(image_format=mp.ImageFormat.SRGB,
                         data=cv2.cvtColor(image, cv2.COLOR_BGR2RGB)), timestamp_ms)
            index = select_right_hand(result)
            landmarks = None if index is None else result.hand_landmarks[index]
            score = None if index is None else max(
                category.score for category in result.handedness[index]
                if category.category_name == "Right")
            frame = tracker.update(landmarks, timestamp_ms, score)
            write_csv_frame(writer, frame)
            if args.json:
                print(json.dumps(frame, allow_nan=False, separators=(",", ":")), flush=True)
            if now - last_flush >= 1:
                recording.flush()
                last_flush = now
            frame_index += 1
            loop_dt = time.perf_counter() - previous_loop
            fps = 0.9 * fps + 0.1 / max(loop_dt, 1e-6) if fps else 1 / max(loop_dt, 1e-6)
            previous_loop = time.perf_counter()
            if not args.headless:
                display = cv2.flip(image, 1)
                if not args.no_trails:
                    trails.update(frame)
                    trails.draw(display, timestamp_ms)
                draw_tracking(display, landmarks, frame, fps)
                cv2.imshow("uHand UNO - Right Hand Motion", display)
                if cv2.waitKey(1) & 0xFF in (ord("q"), 27):
                    break
        print(f"Saved {frame_index} frames to {output.resolve()}", file=sys.stderr)


def main():
    try:
        run(parse_args())
    except KeyboardInterrupt:
        print("Stopped; recording closed.", file=sys.stderr)
    except BrokenPipeError:
        # A downstream JSON consumer may intentionally stop reading.
        sys.stdout = open("/dev/null", "w")
    except (OSError, RuntimeError, ValueError) as error:
        raise SystemExit(f"Tracker error: {error}") from error


if __name__ == "__main__":
    main()
