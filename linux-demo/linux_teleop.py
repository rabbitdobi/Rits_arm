"""Calibrate and run a supervised D455 → XM430 / Arduino bench demo."""

import argparse
from collections import deque
from contextlib import ExitStack
import json
from pathlib import Path
import sys
import time

from xm430_arm_demo import (
    ArmBus, DemoError, JOINTS, MAX_DEMO_TRAVEL, START_TOLERANCE,
    TRACKING_TOLERANCE, require_near,
)

HERE = Path(__file__).resolve().parent
VISION = HERE / "mediapipe" / "VincentMediapipe"
AXES = ("x+", "x-", "y+", "y-", "z+", "z-")
TEACH_M = 0.020
GAIN = 0.25
INTERVAL = 0.10
MAX_GAP = 0.35
MAX_AXIS_STEP = 3


class LocalMapping:
    """Interpolate in the six taught directions around the neutral robot pose."""

    def __init__(self, poses, limits):
        import numpy as np

        if not isinstance(poses, dict) or set(poses) != {"neutral", *AXES}:
            raise DemoError("Calibration needs the neutral pose and all six direction poses")
        for name, pose in poses.items():
            if not isinstance(pose, dict) or set(pose) != {str(motor) for motor in JOINTS}:
                raise DemoError(f"Invalid motor IDs in pose {name}")
            for motor, (low, high) in limits.items():
                value = pose[str(motor)]
                if type(value) is not int or not low <= value <= high:
                    raise DemoError(f"{name}: ID {motor:03} is outside its configured limits")
        self.np = np
        self.neutral = {motor: poses["neutral"][str(motor)] for motor in JOINTS}
        center = np.array(list(self.neutral.values()), dtype=float)
        self.offsets = np.array([[poses[name][str(motor)] for motor in JOINTS]
                                 for name in AXES], dtype=float) - center
        excursions = np.max(np.abs(self.offsets), axis=1)
        if np.any(excursions <= START_TOLERANCE) or np.any(excursions > MAX_DEMO_TRAVEL):
            raise DemoError("Each direction must move at least one joint by >6 and all by <=114 counts")
        positive, negative = self.offsets[::2], self.offsets[1::2]
        if np.any(np.sum(positive * negative, axis=1) >= 0):
            raise DemoError("Each positive/negative pair must move in opposing directions")
        if np.linalg.svd(positive - negative, compute_uv=False)[-1] < 8:
            raise DemoError("The three taught directions are too similar to control independently")

    def project(self, offset):
        offset = self.np.asarray(offset, dtype=float)
        return offset / max(1.0, self.np.abs(offset).sum() / TEACH_M)

    def goal(self, offset):
        scaled = self.project(offset) / TEACH_M
        weights = self.np.maximum(0, self.np.column_stack((scaled, -scaled)).ravel())
        return {motor: round(self.neutral[motor] + value)
                for motor, value in zip(JOINTS, weights @ self.offsets)}

    def step(self, offset, desired, previous):
        current = self.goal(offset)
        if previous != current:
            # The physical start can differ from the taught neutral by a few counts.
            goal = {motor: value + max(-MAX_AXIS_STEP, min(MAX_AXIS_STEP, current[motor] - value))
                    for motor, value in previous.items()}
            return offset, goal
        delta = desired - offset
        distance = self.np.abs(delta).sum()
        # The steepest taught segment bounds the encoder change in every direction.
        step_m = (MAX_AXIS_STEP - 1) * TEACH_M / MAX_DEMO_TRAVEL
        offset = offset + delta / max(1.0, distance / step_m)
        return offset, self.goal(offset)


def teach(bus, limits, path):
    if path.exists():
        raise DemoError(f"{path} already exists; choose a new path")
    prompts = (
        ("neutral", "supported neutral pose"),
        ("x+", "20 mm to camera image-right"), ("x-", "20 mm to camera image-left"),
        ("y+", "20 mm down"), ("y-", "20 mm up"),
        ("z+", "20 mm away from D455"), ("z-", "20 mm toward D455"),
    )
    poses = {}
    for name, prompt in prompts:
        input(f"Keep torque off; place tool at {prompt}. Press Enter when steady: ")
        pose = bus.capture(limits)
        poses[name] = {str(motor): value for motor, value in pose.items()}
        print(f"{name}: {pose}")
    LocalMapping(poses, limits)
    # Verify the arm is back at the neutral pose before handing off to the live demo.
    input("Support the arm at the original neutral pose, then press Enter: ")
    require_near({int(k): v for k, v in poses["neutral"].items()}, bus.capture(limits),
                 START_TOLERANCE, "Return to the taught neutral pose")
    with path.open("x", encoding="utf-8") as out:
        json.dump({"version": 1, "poses": poses}, out, indent=2)
        out.write("\n")
    print(f"Saved {path}")


class LiveControl:
    def __init__(self, bus, limits, mapping, hand):
        self.bus, self.limits, self.mapping, self.hand = bus, limits, mapping, hand
        self.samples = deque(maxlen=12)
        self.active = False
        self.last_frame = self.last_send = None
        self.last_color_number = None
        self.last_digits = [180] * 5  # Operator confirms the firmware has initialized to open.
        self.origin = self.offset = self.reference = self.goal = None
        if mapping is not None:
            self.offset = mapping.np.zeros(3)
        self.status = "PAUSED | G engage, S pause, Q exit"

    def pause(self, reason):
        self.active = False
        self.samples.clear()
        self.status = f"PAUSED: {reason} | G to engage"

    def palm(self, frame):
        depth = frame.get("depth", {})
        number = depth.get("color_frame_number")
        duplicate = number is None or self.last_color_number == number
        self.last_color_number = number
        point = depth.get("points", {}).get("Palm", {})
        if duplicate or not frame.get("tracked") or not point.get("valid"):
            return None
        xyz = self.mapping.np.array([point.get(k) for k in ("X_m", "Y_m", "Z_m")], dtype=float)
        if not self.mapping.np.isfinite(xyz).all() or not .55 <= xyz[2] <= 1.2:
            return None
        return xyz

    def frame(self, frame, key, captured, now):
        gap = self.last_frame is not None and not 0 < captured - self.last_frame <= MAX_GAP
        self.last_frame = captured
        if key in (ord("s"), ord("S"), ord("o"), ord("O"), ord("f"), ord("F"), ord("r"), ord("R")):
            self.pause("operator input")
            return
        if gap or now - captured > MAX_GAP:
            self.pause("camera or processing gap")
            return
        fingers = frame.get("targets", {}).get("fingers", {})
        digits = fingers.get("targets_0_180") if fingers.get("valid") else None
        if self.hand is not None and (not isinstance(digits, list) or len(digits) != 5
                                      or not all(0 <= angle <= 180 for angle in digits)):
            self.pause("hold tracked hand; calibrate O/F for fingers")
            return
        if self.bus is not None:
            palm = self.palm(frame)
            if palm is None:
                self.pause("palm depth lost")
                return
            np = self.mapping.np
            if self.samples and np.linalg.norm(palm - self.samples[-1][1]) > .045:
                self.pause("depth jump")
                return
            self.samples.append((captured, palm))
        if key in (ord("g"), ord("G")) and not self.active:
            if self.bus is not None:
                if len(self.samples) < 6 or self.samples[-1][0] - self.samples[0][0] < .16:
                    self.status = "PAUSED: hold the palm still, then press G"
                    return
                samples = np.array([sample for _, sample in self.samples])
                if np.max(np.ptp(samples, axis=0)) > .025:
                    self.status = "PAUSED: hold the palm still, then press G"
                    return
                if self.goal is None:
                    self.goal = self.bus.enable(self.mapping.neutral, self.limits)
                    # Use the captured encoder position as the initial goal, then slew
                    # the few permissible counts toward the calibrated neutral.
                require_near(self.goal, self.bus.positions(), TRACKING_TOLERANCE, "Resume position check failed")
                self.origin = np.median(samples, axis=0)
                self.reference = self.offset.copy()
            self.last_send = now
            self.active = True
            self.status = "LIVE | S pause, Q exit and hold"
            return
        if not self.active or now - self.last_send < INTERVAL:
            return
        if self.bus is not None:
            require_near(self.goal, self.bus.positions(), TRACKING_TOLERANCE, "Position tracking failed")
            desired = self.mapping.project(self.reference + GAIN * (palm - self.origin))
            self.offset, next_goal = self.mapping.step(self.offset, desired, self.goal)
            if next_goal != self.goal:
                self.bus.send_pose(next_goal)
                self.goal = next_goal
        if self.hand is not None:
            if self.hand.in_waiting:
                self.hand.read(self.hand.in_waiting)
            self.last_digits = [last + max(-8, min(8, round(target) - last))
                                for last, target in zip(self.last_digits, digits)]
            packet = (",".join(map(str, self.last_digits)) + "\n").encode("ascii")
            if self.hand.write(packet) != len(packet):
                raise DemoError("Arduino serial write incomplete")
        self.last_send = now


def arguments():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("teach", "release"):
        sub = commands.add_parser(name)
        sub.add_argument("--arm-port", required=True)
        if name == "teach":
            sub.add_argument("--calibration", type=Path, required=True)
    run = commands.add_parser("run")
    run.add_argument("--arm-port")
    run.add_argument("--calibration", type=Path)
    run.add_argument("--hand-port")
    args = parser.parse_args()
    if args.command == "run":
        if not (args.arm_port or args.hand_port) or bool(args.arm_port) != bool(args.calibration):
            parser.error("run needs --hand-port and/or --arm-port with --calibration")
        if args.arm_port and args.hand_port and Path(args.arm_port).resolve() == Path(args.hand_port).resolve():
            parser.error("Use different serial devices for the arm and hand")
    return args


def main():
    args = arguments()
    try:
        with ExitStack() as stack:
            bus = limits = mapping = hand = None
            if args.arm_port:
                import dynamixel_sdk

                bus = ArmBus(dynamixel_sdk, args.arm_port)
                stack.callback(bus.close)
                limits = bus.inspect()
            if args.command == "teach":
                teach(bus, limits, args.calibration)
                return 0
            if args.command == "release":
                if input("Physically support the arm against gravity. Type RELEASE: ") == "RELEASE":
                    bus.release()
                    print("Torque released.")
                return 0
            if args.calibration:
                calibration = json.loads(args.calibration.read_text(encoding="utf-8"))
                if not isinstance(calibration, dict) or calibration.get("version") != 1:
                    raise DemoError("Unknown calibration file format")
                mapping = LocalMapping(calibration.get("poses"), limits)
                bus.capture(limits)
            if input("Clear the tool path, keep the arm supported until torque is enabled, and have the power cutoff ready. Type MOVE: ") != "MOVE":
                return 0
            if args.hand_port:
                import serial

                hand = stack.enter_context(serial.Serial(args.hand_port, 115200, timeout=0,
                                                         write_timeout=.15, exclusive=True))
                time.sleep(2)  # USB serial may reset the Uno and move fingers open.
                if input("Check that all five fingers are open. Type OPEN: ") != "OPEN":
                    return 0
            if bus is not None:
                stack.callback(report_hold, bus, args.arm_port)
            sys.path.insert(0, str(VISION))
            from main import parse_args, run

            vision_args = ["--realsense", "--no-trails"]
            if hand is not None:
                vision_args.append("--unified-preview")
            run(parse_args(vision_args), live=LiveControl(bus, limits, mapping, hand))
    except KeyboardInterrupt:
        return 130
    except (RuntimeError, OSError, ValueError, EOFError, ImportError) as exc:
        print(f"Stopped: {exc}", file=sys.stderr)
        return 1
    return 0


def report_hold(bus, dev):
    if bus.torque_may_be_on:
        print(f"Arm torque may still be on. Support it before using the release command on {dev}.",
              file=sys.stderr)


if __name__ == "__main__":
    raise SystemExit(main())
