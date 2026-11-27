"""Explicitly unverified four-joint demo geometry. No actuator interfaces."""

import copy
import json
import math
from pathlib import Path

DEFAULT_CONFIG = Path(__file__).with_name("teleop_model.json")


def wrap(angle):
    return (angle + math.pi) % (2 * math.pi) - math.pi


class ArmModel:
    def __init__(self, config=None):
        if config is None:
            config = json.loads(DEFAULT_CONFIG.read_text())
        self.config = copy.deepcopy(config)
        try:
            if config["simulation_only"] is not True or config["geometry_verified"] is not False:
                raise ValueError("This controller only supports an unverified simulation model")
            for key, count in (("links_m", 3), ("joint_min_rad", 4), ("joint_max_rad", 4),
                               ("origin_target_m", 3), ("translation_gain", 3), ("wrist_servo_limits_deg", 2)):
                values = config[key]
                if len(values) != count or not all(math.isfinite(v) for v in values):
                    raise ValueError(f"Invalid {key}")
            for key in ("tool_pitch_down_rad", "max_joint_speed_rad_s", "wrist_servo_neutral_deg", "wrist_twist_gain"):
                if not math.isfinite(config[key]):
                    raise ValueError(f"Invalid {key}")
            if min(config["links_m"] + config["translation_gain"]) <= 0 or config["max_joint_speed_rad_s"] <= 0:
                raise ValueError("Lengths, gains and speed must be positive")
            if any(lo >= hi for lo, hi in zip(config["joint_min_rad"], config["joint_max_rad"])):
                raise ValueError("Invalid joint limits")
            bounds = config["workspace_m"]
            if len(bounds) != 3 or any(len(b) != 2 or not all(math.isfinite(v) for v in b) or b[0] >= b[1] for b in bounds):
                raise ValueError("Invalid workspace")
            mapping = config["camera_delta_to_robot"]
            if (len(mapping) != 3 or any(len(r) != 3 or any(v not in (-1, 0, 1) for v in r) or sum(abs(v) for v in r) != 1 for r in mapping)
                    or any(sum(abs(mapping[i][j]) for i in range(3)) != 1 for j in range(3))):
                raise ValueError("Axis mapping must be a signed permutation")
            lo, hi = config["wrist_servo_limits_deg"]
            if not 0 <= lo < config["wrist_servo_neutral_deg"] < hi <= 180:
                raise ValueError("Invalid wrist preview limits")
        except (KeyError, TypeError) as error:
            raise ValueError(f"Invalid model configuration: {error}") from error

    def forward(self, joints):
        if len(joints) != 4 or not all(math.isfinite(v) for v in joints):
            raise ValueError("Expected four finite joint angles")
        base, shoulder, elbow, wrist = joints
        upper, fore, tool = self.config["links_m"]
        r = z = 0.
        points = [[0., 0., 0.]]
        for dr, dz in ((upper * math.sin(shoulder), upper * math.cos(shoulder)),
                       (fore * math.cos(shoulder + elbow), -fore * math.sin(shoulder + elbow)),
                       (tool * math.cos(shoulder + elbow + wrist), -tool * math.sin(shoulder + elbow + wrist))):
            r += dr
            z += dz
            points.append([r * math.cos(base), r * math.sin(base), z])
        return points

    def solve(self, target, previous=None):
        result = {"valid": False, "reason": "invalid_position", "joints_rad": None}
        if len(target) != 3 or not all(math.isfinite(v) for v in target):
            return result
        if any(not lo <= v <= hi for v, (lo, hi) in zip(target, self.config["workspace_m"])):
            return dict(result, reason="outside_workspace")
        x, y, z = target
        radius = math.hypot(x, y)
        upper, fore, tool = self.config["links_m"]
        pitch = self.config["tool_pitch_down_rad"]
        rw, zw = radius - tool * math.cos(pitch), z + tool * math.sin(pitch)
        cosine = (rw * rw + zw * zw - upper * upper - fore * fore) / (2 * upper * fore)
        if not -1 - 1e-9 <= cosine <= 1 + 1e-9:
            return dict(result, reason="unreachable")
        base = math.atan2(y, x)
        candidates = []
        for bend in (math.acos(max(-1., min(1., cosine))), -math.acos(max(-1., min(1., cosine)))):
            heading = math.atan2(zw, rw) - math.atan2(fore * math.sin(bend), upper + fore * math.cos(bend))
            shoulder = wrap(math.pi / 2 - heading)
            elbow = wrap(-bend - math.pi / 2)
            wrist = wrap(pitch - shoulder - elbow)
            joints = [base, shoulder, elbow, wrist]
            if all(lo - 1e-9 <= value <= hi + 1e-9 for value, lo, hi in zip(joints, self.config["joint_min_rad"], self.config["joint_max_rad"])):
                candidates.append(joints)
        if not candidates:
            return dict(result, reason="joint_limits")
        previous = previous if previous is not None else [0., 0., 0., 0.]
        best = min(candidates, key=lambda q: sum((a - b) ** 2 for a, b in zip(q, previous)))
        return dict(valid=True, reason="ok", joints_rad=best)
