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
from arm_retarget_replay import DEFAULT_GAIN, WristRetargetPreview

SCRIPT_DIR = Path(__file__).resolve().parent


def positive_distance(value):
    try:
        number = float(value)
    except ValueError:
        raise argparse.ArgumentTypeError("Distance must be positive and finite")
    if not math.isfinite(number) or number <= 0:
        raise argparse.ArgumentTypeError("Distance must be positive and finite")
    return number


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--camera", type=int, default=0, help="Camera index (default: 0)")
    source.add_argument("--video", type=Path, help="Read a constant-frame-rate video instead")
    source.add_argument("--realsense", action="store_true", help="Use aligned D455 color/depth via RealSense SDK")
    parser.add_argument("--max-frames", type=int, help="Stop after this many processed frames")
    parser.add_argument("--depth-samples-every", type=int,
                        help="D455 diagnostic: save original RGB/depth/landmarks every N processed frames")
    parser.add_argument("--model", type=Path, default=SCRIPT_DIR.parent / "models" / "hand_landmarker.task")
    parser.add_argument("--csv", type=Path, help="New CSV path (default: output/fingers-TIMESTAMP.csv)")
    parser.add_argument("--json", action="store_true", help="Emit one JSON object per frame on stdout")
    parser.add_argument("--headless", action="store_true", help="Disable the preview window")
    parser.add_argument("--no-trails", action="store_true", help="Disable glowing trails")
    parser.add_argument("--record", nargs="?", const="auto", metavar="MP4",
                        help="Record annotated video; optional new .mp4 path (default: output/demo-TIMESTAMP.mp4)")
    parser.add_argument("--control-preview", action="store_true",
                        help="Show estimated palm distance and finger flexion; C calibrates, R resets")
    parser.add_argument("--reference-cm", type=positive_distance, default=40.,
                        help="Measured camera-to-palm distance when pressing C (default: 40 cm)")
    parser.add_argument("--unified-preview", action="store_true", help="Simulation-only fingers, wrist and arm; O/F/W/Space calibrate, R resets")
    parser.add_argument("--teleop-config", type=Path, help="Unverified simulation model JSON")
    parser.add_argument("--arm-tracking", action="store_true", help="Track human shoulders, elbows and wrists; sensor XYZ requires D455")
    parser.add_argument("--arm-retarget", action="store_true",
                        help="Preview four robot axes from D455 arm tracking; N recenters")
    parser.add_argument("--arm-retarget-gain", type=positive_distance, default=DEFAULT_GAIN,
                        help="Scale wrist displacement in the four-axis preview")
    parser.add_argument("--pose-model", type=Path, default=SCRIPT_DIR.parent / "models" / "pose_landmarker_lite.task")
    parser.add_argument("--arm-smoothing-ms", type=float, default=80., help="Human-arm display filter time constant, 0 disables (raw measurements unchanged)")
    args = parser.parse_args(argv)
    if not math.isfinite(args.arm_smoothing_ms) or args.arm_smoothing_ms < 0:
        parser.error("--arm-smoothing-ms must be finite and nonnegative")
    if args.max_frames is not None and args.max_frames < 1:
        parser.error("--max-frames must be positive")
    if args.depth_samples_every is not None and (not args.realsense or args.depth_samples_every < 1):
        parser.error("--depth-samples-every requires --realsense and a positive interval")
    if args.arm_retarget:
        if not args.realsense:
            parser.error("--arm-retarget requires --realsense")
        args.arm_tracking = True
    return args


def run(args, live=None):
    video_output = None
    if args.record is not None:
        video_output = (SCRIPT_DIR / "output" / f"demo-{datetime.now():%Y%m%d-%H%M%S-%f}.mp4"
                        if args.record == "auto" else Path(args.record))
        if video_output.suffix.lower() != ".mp4":
            raise SystemExit("Recording path must end in .mp4")
        if video_output.exists():
            raise SystemExit(f"Recording already exists: {video_output}. Choose a new --record path.")
    output = args.csv or (SCRIPT_DIR / "output" /
                          f"fingers-{datetime.now():%Y%m%d-%H%M%S-%f}.csv")
    if output.exists():
        raise SystemExit(f"Recording already exists: {output}. Choose a new --csv path.")
    control_path = output.with_suffix(".control.jsonl") if args.control_preview else None
    if control_path is not None and control_path.exists():
        raise SystemExit(f"Recording already exists: {control_path}. Choose a new --csv path.")
    target_path = output.with_suffix(".targets.jsonl") if args.unified_preview else None
    target_config_path = output.with_suffix(".targets.config.json") if args.unified_preview else None
    human_path = output.with_suffix(".human-arm.jsonl") if args.arm_tracking else None
    human_csv_path = output.with_suffix(".human-arm.csv") if args.arm_tracking else None
    depth_path = output.with_suffix(".depth.csv") if args.realsense else None
    depth_metadata_path = output.with_suffix(".depth.json") if args.realsense else None
    samples_path = output.with_suffix(".depth-samples") if args.depth_samples_every else None
    paths = [p for p in (output, control_path, depth_path, depth_metadata_path, video_output, samples_path, target_path, target_config_path, human_path, human_csv_path) if p is not None]
    if len({p.resolve() for p in paths}) != len(paths):
        raise SystemExit("Recording output paths must be distinct")
    for path in (depth_path, depth_metadata_path, samples_path, target_path, target_config_path, human_path, human_csv_path):
        if path is not None and path.exists():
            raise SystemExit(f"Recording already exists: {path}. Choose a new --csv path.")
    if not args.model.is_file():
        raise SystemExit(f"Model file not found: {args.model}. See mediapipe/VincentMediapipe/README.md.")
    if args.arm_tracking and not args.pose_model.is_file():
        raise SystemExit(f"Pose model file not found: {args.pose_model}. See docs/human-arm-tracking.md.")
    if args.video is not None and not args.video.is_file():
        raise SystemExit(f"Video file not found: {args.video}")

    # Keep --help available before optional vision packages are installed.
    import cv2
    import mediapipe as mp
    from effects import FingerTrails, draw_control, draw_tracking, draw_metric_depth
    from control import ControlTracker
    from recording import VideoRecorder

    simulation_config = None
    if args.teleop_config and (args.unified_preview or args.arm_retarget):
        simulation_config = json.loads(args.teleop_config.read_text())
    unified = retarget = None
    if args.arm_retarget:
        from human_arm_view import draw_retarget_status
        retarget = WristRetargetPreview(use_filtered=args.arm_smoothing_ms > 0,
                                       gain=args.arm_retarget_gain, config=simulation_config)
    if args.unified_preview:
        from unified_control import UnifiedController
        from unified_view import draw_unified_panel
        unified = UnifiedController(simulation_config)

    with ExitStack() as stack:
        created_paths = []
        if args.realsense:
            from realsense_source import RealSenseSource, DEPTH_FIELDS, write_depth_csv, restore_user_ownership, ensure_output_directory, save_depth_sample
            stack.callback(restore_user_ownership, created_paths)
            cap = RealSenseSource() if live is None else RealSenseSource(frame_timeout_ms=350)
        else:
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
        pose_detector = arm_tracker = None
        if args.arm_tracking:
            from human_arm import HumanArmTracker, select_pose, HUMAN_ARM_FIELDS, write_human_arm_csv, hand_wrists_from_result
            from human_arm_view import draw_human_arm_overlay, draw_human_arm_depth
            pose_options = mp.tasks.vision.PoseLandmarkerOptions(
                base_options=mp.tasks.BaseOptions(model_asset_path=str(args.pose_model)),
                running_mode=mp.tasks.vision.RunningMode.VIDEO, num_poses=2,
                min_pose_detection_confidence=.6, min_pose_presence_confidence=.6,
                min_tracking_confidence=.6)
            pose_detector = stack.enter_context(mp.tasks.vision.PoseLandmarker.create_from_options(pose_options))
            arm_tracker = HumanArmTracker(smoothing_ms=args.arm_smoothing_ms)
        if not args.headless:
            stack.callback(cv2.destroyAllWindows)
        if args.realsense:
            ensure_output_directory(output.parent, created_paths)
        else:
            output.parent.mkdir(parents=True, exist_ok=True)
        recording = stack.enter_context(output.open("x", newline="", encoding="utf-8"))
        created_paths.append(output)
        control_log = (stack.enter_context(control_path.open("x", encoding="utf-8"))
                       if control_path is not None else None)
        if control_path is not None:
            created_paths.append(control_path)
        target_log = None
        if target_path is not None:
            target_log = stack.enter_context(target_path.open("x", encoding="utf-8"))
            created_paths.append(target_path)
            with target_config_path.open("x", encoding="utf-8") as config_file:
                created_paths.append(target_config_path)
                json.dump(unified.model.config, config_file, indent=2, allow_nan=False)
            print(f"SIMULATION ONLY: {target_path.resolve()}\nHold poses steady. O=open, F=fist, W=wrist neutral, Space=arm origin, R=reset", file=sys.stderr)
        human_log = human_writer = None
        if human_path is not None:
            human_log = stack.enter_context(human_path.open("x", encoding="utf-8"))
            created_paths.append(human_path)
            human_csv = stack.enter_context(human_csv_path.open("x", newline="", encoding="utf-8"))
            created_paths.append(human_csv_path)
            human_writer = csv.DictWriter(human_csv, fieldnames=HUMAN_ARM_FIELDS)
            human_writer.writeheader()
            print(f"Human shoulders/elbows/wrists: {human_path.resolve()}\nKeep the full arm visible; XYZ is sensor measured, not robot targets.", file=sys.stderr)
        depth_log = None
        if depth_path is not None:
            depth_log = stack.enter_context(depth_path.open("x", newline="", encoding="utf-8"))
            created_paths.append(depth_path)
            depth_writer = csv.DictWriter(depth_log, fieldnames=DEPTH_FIELDS)
            depth_writer.writeheader()
            with depth_metadata_path.open("x", encoding="utf-8") as metadata_file:
                created_paths.append(depth_metadata_path)
                json.dump(cap.metadata, metadata_file, indent=2, allow_nan=False)
            print(f"D455 metric data: {depth_path.resolve()}", file=sys.stderr)
        if samples_path is not None:
            samples_path.mkdir(exist_ok=False)
            created_paths.append(samples_path)
            print(f"Original-frame diagnostics: {samples_path.resolve()}", file=sys.stderr)
        controller = ControlTracker(args.reference_cm) if args.control_preview else None
        writer = csv.DictWriter(recording, fieldnames=CSV_FIELDS)
        writer.writeheader()
        print(f"Recording: {output.resolve()}\nPress q / Esc or Ctrl-C to stop.", file=sys.stderr)
        if controller is not None and not args.realsense:
            print(f"Control preview: hold palm at {args.reference_cm:g} cm, face camera, press C. "
                  f"R resets. No motor output.\nControl log: {control_path.resolve()}", file=sys.stderr)
        tracker, trails = MotionTracker(), FingerTrails()
        start = previous_loop = time.perf_counter()
        last_flush = start
        frame_index, last_timestamp, fps = 0, -1, 0.0
        recorder = None
        stop_reason = "video_end"
        if args.max_frames is not None:
            print(f"Auto-save/end after {args.max_frames} processed frames; the preview will close normally.", file=sys.stderr)
        show_stabilized = True

        while True:
            success, image = cap.read()
            now = time.perf_counter()
            if not success:
                if args.video is None or frame_index == 0:
                    raise SystemExit("Could not read a frame from video/camera.")
                break
            elapsed_ms = (frame_index * 1000 / video_fps if video_fps is not None
                          else (now - start) * 1000)
            if args.realsense:
                elapsed_ms = cap.timestamp_ms
            timestamp_ms = max(last_timestamp + 1, int(elapsed_ms))
            last_timestamp = timestamp_ms
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB,
                                data=cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
            result = detector.detect_for_video(mp_image, timestamp_ms)
            index = select_right_hand(result, prefer_largest=args.realsense)
            landmarks = None if index is None else result.hand_landmarks[index]
            world_landmarks = (None if index is None or not getattr(result, "hand_world_landmarks", None)
                               else result.hand_world_landmarks[index])
            score = None if index is None else max(
                category.score for category in result.handedness[index]
                if category.category_name == "Right")
            frame = tracker.update(landmarks, timestamp_ms, score, world_landmarks=world_landmarks)
            if args.realsense:
                frame["depth"] = cap.measure(landmarks)
                write_depth_csv(depth_writer, frame["depth"], timestamp_ms, frame["tracked"], score)
            if pose_detector is not None:
                pose_result = pose_detector.detect_for_video(mp_image, timestamp_ms)
                pose_index = select_pose(pose_result)
                body_landmarks = None if pose_index is None else pose_result.pose_landmarks[pose_index]
                depth_args = ((cap.raw, cap.scale,
                               lambda pixel, z: cap.rs.rs2_deproject_pixel_to_point(cap.intrinsics, pixel, z))
                              if args.realsense else ())
                frame["human_arm"] = arm_tracker.update(body_landmarks, timestamp_ms, *depth_args, hand_wrists=hand_wrists_from_result(result))
                if retarget is not None:
                    frame["human_arm"]["robot_arm_preview"] = retarget.update(frame["human_arm"])
                human_log.write(json.dumps(frame["human_arm"], allow_nan=False, separators=(",", ":")) + "\n")
                write_human_arm_csv(human_writer, frame["human_arm"])
            if controller is not None:
                world = None if index is None else result.hand_world_landmarks[index]
                height, width = image.shape[:2]
                control_frame = controller.update(landmarks, world, timestamp_ms, (width, height))
                if args.realsense:
                    palm = frame["depth"]["points"].get("Palm", {})
                    distance = palm.get("Z_m")
                    control_frame.update(method="realsense_depth", status="sensor_depth" if distance is not None else "depth_unavailable",
                                         distance_cm=distance * 100 if distance is not None else None,
                                         delta_cm=None, calibration=None, calibration_samples=0)
                frame["control"] = control_frame
                control_log.write(json.dumps(dict(timestamp_ms=timestamp_ms, **control_frame),
                                             allow_nan=False, separators=(",", ":")) + "\n")
            if unified is not None:
                world = None if index is None else result.hand_world_landmarks[index]
                frame["targets"] = unified.update(world, frame.get("depth"), timestamp_ms)
                target_log.write(json.dumps(frame["targets"], allow_nan=False, separators=(",", ":")) + "\n")
            write_csv_frame(writer, frame)
            if samples_path is not None and frame_index % args.depth_samples_every == 0:
                save_depth_sample(samples_path, frame_index, cap.raw, image, cap.scale,
                                  landmarks, frame, created_paths, native_raw=cap.native_raw)
            if args.json:
                print(json.dumps(frame, allow_nan=False, separators=(",", ":")), flush=True)
            if now - last_flush >= 1:
                recording.flush()
                if human_log is not None:
                    human_log.flush()
                    human_csv.flush()
                if target_log is not None:
                    target_log.flush()
                if control_log is not None:
                    control_log.flush()
                if depth_log is not None:
                    depth_log.flush()
                last_flush = now
            frame_index += 1
            loop_dt = time.perf_counter() - previous_loop
            fps = 0.9 * fps + 0.1 / max(loop_dt, 1e-6) if fps else 1 / max(loop_dt, 1e-6)
            previous_loop = time.perf_counter()
            if not args.headless or video_output is not None:
                display = cv2.flip(image, 1)
                if not args.no_trails:
                    trails.update(frame)
                    trails.draw(display, timestamp_ms)
                if args.arm_tracking:
                    draw_human_arm_overlay(display, frame["human_arm"], fps, show_stabilized=show_stabilized)
                    if args.max_frames is not None:
                        remaining_seconds=max(0,args.max_frames-frame_index)/max(fps,1.)
                        h,w=display.shape[:2]
                        cv2.rectangle(display,(0,h-58),(w,h-32),(20,25,20),-1)
                        cv2.putText(display,f'Auto-save/end in ~{remaining_seconds:.0f}s | Q saves now',
                                    (8,h-41),cv2.FONT_HERSHEY_SIMPLEX,.44,(80,210,255),1,cv2.LINE_AA)
                else:
                    draw_tracking(display, landmarks, frame, fps)
                if controller is not None and not args.realsense:
                    draw_control(display, control_frame)
                if args.realsense:
                    import numpy as np
                    depth_display = cap.depth_view()
                    if args.arm_tracking:
                        draw_human_arm_depth(depth_display, frame["human_arm"], show_stabilized=show_stabilized)
                    else:
                        draw_metric_depth(depth_display, frame["depth"], frame.get("control", {}).get("flexion", {}))
                    display = np.hstack((display, depth_display))
                if unified is not None:
                    import numpy as np
                    display = np.hstack((display, draw_unified_panel(frame["targets"], unified.model, display.shape[0])))
                if retarget is not None:
                    display = draw_retarget_status(display, frame["human_arm"]["robot_arm_preview"])
                if live is not None:
                    cv2.putText(display, live.status, (8, display.shape[0] - 12),
                                cv2.FONT_HERSHEY_SIMPLEX, .48, (0, 230, 255), 1, cv2.LINE_AA)
                if video_output is not None:
                    if recorder is None:
                        height, width = display.shape[:2]
                        if args.realsense:
                            ensure_output_directory(video_output.parent, created_paths)
                        recorder = VideoRecorder(video_output, video_fps or 30, (width, height))
                        created_paths.append(video_output)
                        stack.callback(recorder.close)
                        print(f"Video recording: {video_output.resolve()}", file=sys.stderr)
                    recorder.write(display, elapsed_ms)
            if not args.headless:
                window_title = "Human Arm - Shoulder Elbow Wrist" if args.arm_tracking else "uHand UNO - Right Hand Motion"
                cv2.imshow(window_title, display)
                key = cv2.waitKey(1) & 0xFF
                if key in (ord("q"), 27):
                    stop_reason = "user_exit"
                    break
                if live is not None:
                    if cv2.getWindowProperty(window_title, cv2.WND_PROP_VISIBLE) < 1:
                        stop_reason = "window_closed"
                        break
                    live.frame(frame, key, now, time.perf_counter())
                if args.arm_tracking and key in (ord("v"), ord("V")):
                    show_stabilized = not show_stabilized
                if retarget is not None and key in (ord("n"), ord("N")):
                    retarget.recenter()
                if unified is not None:
                    if key in (ord("o"), ord("O")):
                        unified.calibrate_fingers("open")
                    elif key in (ord("f"), ord("F")):
                        unified.calibrate_fingers("fist")
                    elif key in (ord("w"), ord("W")):
                        unified.calibrate_wrist()
                    elif key == 32:
                        unified.capture_origin()
                    elif key in (ord("r"), ord("R")):
                        unified.reset()
                if controller is not None and not args.realsense:
                    if key in (ord("c"), ord("C")):
                        controller.request_calibration()
                    elif key in (ord("r"), ord("R")):
                        controller.reset()
            if args.max_frames is not None and frame_index >= args.max_frames:
                stop_reason = "frame_limit"
                break
        if arm_tracker is not None:
            quality = arm_tracker.quality.session
            total = quality['frames']
            if total:
                print(f"Right arm session: depth complete {quality['depth_complete_frames']}/{total} "
                      f"({100*quality['depth_complete_frames']/total:.1f}%), "
                      f"geometry valid {quality['geometry_valid_frames']}/{total}. "
                      "Availability is not accuracy.", file=sys.stderr)
        print(f"Stop reason: {stop_reason} (normal recording end).", file=sys.stderr)
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
