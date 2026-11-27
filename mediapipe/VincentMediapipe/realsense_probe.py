"""Check a D455's synchronized RGB/depth streams without ROS or MediaPipe."""

import argparse
import csv
from datetime import datetime
import json
import math
import os
from pathlib import Path
import sys
import time


def depth_summary(raw, scale):
    import numpy as np

    if not math.isfinite(scale) or scale <= 0:
        raise ValueError("Depth scale must be positive and finite")
    if raw.ndim != 2 or not raw.size:
        raise ValueError("Expected a nonempty two-dimensional depth image")
    height, width = raw.shape
    w, h = max(1, int(width * .06)), max(1, int(height * .06))
    x, y = (width - w) // 2, (height - h) // 2
    roi = raw[y:y + h, x:x + w]
    valid = np.isfinite(roi) & (roi > 0)
    fraction = float(valid.mean())
    meters = float(np.median(roi[valid])) * scale if fraction >= .6 else None
    return {"center_m": meters, "center_valid_fraction": fraction,
            "valid_fraction": float((np.isfinite(raw) & (raw > 0)).mean())}


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frames", type=int, default=90, help="Frames to capture after warmup (default: 90)")
    parser.add_argument("--preview", action="store_true", help="Show RGB and aligned depth; Q/Esc finishes")
    parser.add_argument("--output", type=Path, help="New output directory; never overwritten")
    args = parser.parse_args()
    if args.frames < 1:
        parser.error("--frames must be positive")
    if args.output is None:
        args.output = Path(__file__).resolve().parent / "output" / f"realsense-{datetime.now():%Y%m%d-%H%M%S-%f}"
    if args.output.exists():
        parser.error(f"Output already exists: {args.output}")
    return args


def run(args):
    import cv2
    import numpy as np
    import pyrealsense2 as rs

    context = rs.context()
    devices = [device for device in context.query_devices()
               if "D455" in device.get_info(rs.camera_info.name)]
    if not devices:
        raise RuntimeError("SDK cannot access a D455. Check USB connection. On macOS, USB access may require running this probe from Terminal with sudo.")
    if len(devices) != 1:
        raise RuntimeError("Connect only one D455 for this initial probe.")
    device = devices[0]
    pipeline = rs.pipeline(context)
    config = rs.config()
    config.enable_device(device.get_info(rs.camera_info.serial_number))
    config.enable_stream(rs.stream.depth, 640, 480, rs.format.z16, 30)
    config.enable_stream(rs.stream.color, 640, 480, rs.format.bgr8, 30)
    started = False
    created_output = False
    frames_log = []
    try:
        profile = pipeline.start(config)
        started = True
        sensor = profile.get_device().first_depth_sensor()
        scale = sensor.get_depth_scale()
        align = rs.align(rs.stream.color)
        colorizer = rs.colorizer()
        # Discard startup auto-exposure frames, not just a single lucky frame.
        for _ in range(30):
            pipeline.wait_for_frames(10000)
        args.output.mkdir(parents=True, exist_ok=False)
        created_output = True
        started_at = time.monotonic()
        print(f"Reading D455 at 640x480 / 30 FPS; depth unit = {scale:g} meters")
        for i in range(args.frames):
            aligned = align.process(pipeline.wait_for_frames(10000))
            depth, color = aligned.get_depth_frame(), aligned.get_color_frame()
            if not depth or not color:
                raise RuntimeError("Aligned frameset is missing color or depth")
            raw = np.asanyarray(depth.get_data()).copy()
            rgb = np.asanyarray(color.get_data()).copy()
            depth_view = np.asanyarray(colorizer.colorize(depth).get_data())
            depth_view = cv2.cvtColor(depth_view, cv2.COLOR_RGB2BGR)
            summary = depth_summary(raw, scale)
            frames_log.append(dict(frame=i, elapsed_s=time.monotonic() - started_at,
                                   depth_timestamp_ms=depth.get_timestamp(),
                                   color_timestamp_ms=color.get_timestamp(), **summary))
            display = np.hstack((rgb, depth_view))
            center = summary["center_m"]
            text = "Center depth: --" if center is None else f"Center depth: {center * 100:.1f} cm"
            cv2.rectangle(display, (0, 0), (1280, 44), (0, 0, 0), -1)
            cv2.putText(display, text + f" | valid {summary['center_valid_fraction']:.0%}",
                        (12, 29), cv2.FONT_HERSHEY_SIMPLEX, .7, (230, 255, 230), 2)
            for offset in (0, 640):
                cv2.rectangle(display, (offset + 301, 226), (offset + 339, 254), (0, 255, 255), 1)
            if args.preview:
                cv2.imshow("D455: Color | Aligned depth (Q to finish)", display)
                if cv2.waitKey(1) & 0xFF in (ord("q"), 27):
                    break
        for name, frame in (("color.png", rgb), ("aligned-depth.png", depth_view), ("preview.png", display)):
            if not cv2.imwrite(str(args.output / name), frame):
                raise RuntimeError(f"Could not save {name}")
        np.savez_compressed(args.output / "aligned-depth-raw.npz", depth_z16=raw,
                            meters_per_unit=scale)
        intrinsics = depth.profile.as_video_stream_profile().get_intrinsics()
        metadata = {"camera": device.get_info(rs.camera_info.name),
                    "firmware": device.get_info(rs.camera_info.firmware_version),
                    "usb_type": device.get_info(rs.camera_info.usb_type_descriptor),
                    "meters_per_unit": scale, "aligned_to": "color", "frames": len(frames_log),
                    "depth_filtering": "none", "roi_fraction": .06,
                    "intrinsics": {k: getattr(intrinsics, k) for k in ("width", "height", "fx", "fy", "ppx", "ppy", "coeffs")},
                    "distortion_model": str(intrinsics.model), "last_frame": frames_log[-1]}
        (args.output / "metadata.json").write_text(json.dumps(metadata, indent=2, allow_nan=False))
        with (args.output / "measurements.csv").open("x", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=list(frames_log[0]))
            writer.writeheader()
            writer.writerows(frames_log)
        print(f"Captured {len(frames_log)} synchronized frames. Saved: {args.output}")
        print(f"Frames with usable center depth: {sum(row['center_m'] is not None for row in frames_log)}")
    finally:
        if started:
            pipeline.stop()
        if args.preview:
            cv2.destroyAllWindows()
        # Files created during an explicitly elevated USB run belong to the user.
        if created_output and os.geteuid() == 0 and os.environ.get("SUDO_UID") and args.output.is_dir():
            uid, gid = int(os.environ["SUDO_UID"]), int(os.environ["SUDO_GID"])
            for path in [args.output, *args.output.iterdir()]:
                os.chown(path, uid, gid)


if __name__ == "__main__":
    try:
        run(parse_args())
    except (RuntimeError, ImportError, OSError, ValueError) as error:
        print(f"D455 probe failed: {error}", file=sys.stderr)
        raise SystemExit(1)
