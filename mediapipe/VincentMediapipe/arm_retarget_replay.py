"""Preview robot joint angles from a recorded D455 human-arm JSONL file."""

import argparse
import json
import math
from pathlib import Path

from arm_simulation import ArmModel

ARM_JOINTS = ("base", "shoulder", "elbow", "wrist_pitch")
MOTOR_IDS = dict(zip(ARM_JOINTS, (1, 2, 3, 4)))
DEFAULT_GAIN = 0.15


class WristRetargetPreview:
    def __init__(self, side="Right", use_filtered=False, gain=DEFAULT_GAIN, config=None):
        if not math.isfinite(gain) or gain <= 0:
            raise ValueError("Preview gain must be positive and finite")
        self.model = ArmModel(config)
        self.side = side
        self.use_filtered = use_filtered
        self.gain = gain
        self.timestamp_ms = None
        self.recenter()

    def recenter(self):
        self.neutral_wrist = None
        self.previous_joints = None

    def update(self, frame):
        timestamp = frame["timestamp_ms"]
        if not math.isfinite(timestamp) or (
            self.timestamp_ms is not None and timestamp <= self.timestamp_ms
        ):
            raise ValueError("Expected finite, increasing capture timestamps")
        self.timestamp_ms = timestamp
        result = {
            "timestamp_ms": timestamp,
            "simulation_only": True,
            "geometry_verified": False,
            "hardware_enabled": False,
            "reason": "depth_unavailable",
            "translation_gain": self.gain,
            "robot_target_m": None,
            "preview_joint_angles_rad": None,
            "preview_motor_angles_rad": None,
        }
        if frame.get("units") != "m" or frame.get("coordinate_frame") != "d455_color_optical":
            return dict(result, reason="unsupported_coordinate_frame")
        raw = frame.get("arms", {}).get(self.side, {})
        if raw.get("valid") is not True:
            return result
        source = raw
        if self.use_filtered:
            source = frame.get("stabilized", {}).get("arms", {}).get(self.side, {})
            if source.get("valid") is not True:
                return dict(result, reason="filtered_geometry_unavailable")
        wrist = source.get("wrist_relative_shoulder_m")
        if not isinstance(wrist, list) or len(wrist) != 3 or not all(
            type(value) in (int, float) and math.isfinite(value) for value in wrist
        ):
            return dict(result, reason="invalid_wrist_position")
        if self.neutral_wrist is None:
            self.neutral_wrist = wrist.copy()

        delta = [current - neutral for current, neutral in zip(wrist, self.neutral_wrist)]
        config = self.model.config
        target = [
            origin + self.gain * sum(axis * motion for axis, motion in zip(row, delta))
            for origin, row in zip(
                config["origin_target_m"],
                config["camera_delta_to_robot"],
            )
        ]
        if not all(math.isfinite(value) for value in target):
            return dict(result, reason="invalid_target")
        solution = self.model.solve(target, self.previous_joints)
        angles = solution["joints_rad"]
        motor_angles = None
        if solution["valid"]:
            self.previous_joints = angles
            angles = dict(zip(ARM_JOINTS, angles))
            motor_angles = {f"{MOTOR_IDS[joint]:03d}": angle for joint, angle in angles.items()}
        return dict(
            result,
            reason=solution["reason"],
            robot_target_m=target,
            preview_joint_angles_rad=angles,
            preview_motor_angles_rad=motor_angles,
        )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("recording", type=Path, help="Path to a .human-arm.jsonl recording")
    parser.add_argument("--side", choices=("Right", "Left"), default="Right")
    parser.add_argument("--filtered", action="store_true", help="Use recorded stabilized arm geometry")
    parser.add_argument("--gain", type=float, default=DEFAULT_GAIN, help="Scale wrist displacement in the preview")
    args = parser.parse_args()
    try:
        preview = WristRetargetPreview(args.side, args.filtered, args.gain)
    except ValueError as exc:
        parser.error(str(exc))
    with args.recording.open() as recording:
        for line_number, line in enumerate(recording, start=1):
            if not line.strip():
                continue
            try:
                result = preview.update(json.loads(line))
            except (ValueError, KeyError, TypeError, AttributeError) as exc:
                parser.error(f"{args.recording}:{line_number}: {exc}")
            print(json.dumps(result, allow_nan=False))


if __name__ == "__main__":
    main()
