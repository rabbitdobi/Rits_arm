import math
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from arm_retarget_replay import WristRetargetPreview
from main import parse_args


def frame(timestamp, wrist):
    return {
        "timestamp_ms": timestamp,
        "units": "m",
        "coordinate_frame": "d455_color_optical",
        "arms": {"Right": {"valid": wrist is not None, "wrist_relative_shoulder_m": wrist}},
    }


class ArmRetargetTests(unittest.TestCase):
    def test_four_axes_solve_wrist_displacement_and_recenter(self):
        preview = WristRetargetPreview()
        neutral = preview.update(frame(0, [0, 0, 0]))
        moved = preview.update(frame(40, [0.02, 0.04, -0.06]))
        self.assertEqual(moved["reason"], "ok")
        motor_angles = moved["preview_motor_angles_rad"]
        self.assertEqual(list(motor_angles), ["001", "002", "003", "004"])
        self.assertEqual(list(motor_angles.values()), list(moved["preview_joint_angles_rad"].values()))
        self.assertNotEqual(motor_angles, neutral["preview_motor_angles_rad"])
        end = preview.model.forward(list(motor_angles.values()))[-1]
        self.assertLess(math.dist(end, moved["robot_target_m"]), 1e-7)
        preview.recenter()
        centered = preview.update(frame(80, [0.02, 0.04, -0.06]))
        self.assertEqual(centered["robot_target_m"], neutral["robot_target_m"])

    def test_raw_depth_loss_clears_preview_outputs_even_with_filtered_geometry(self):
        preview = WristRetargetPreview(use_filtered=True)
        valid = frame(0, [0, 0, 0])
        valid["stabilized"] = {"arms": valid["arms"]}
        self.assertEqual(preview.update(valid)["reason"], "ok")
        missing = frame(40, None)
        missing["stabilized"] = valid["stabilized"]
        result = preview.update(missing)
        self.assertEqual(result["reason"], "depth_unavailable")
        self.assertIsNone(result["robot_target_m"])
        self.assertIsNone(result["preview_motor_angles_rad"])
        self.assertFalse(result["hardware_enabled"])

    def test_live_flag_enables_body_tracking(self):
        options = parse_args(["--realsense", "--arm-retarget"])
        self.assertTrue(options.arm_tracking)
        self.assertTrue(options.arm_retarget)
