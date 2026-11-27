import json
import math
from pathlib import Path
import sys
from types import SimpleNamespace as P
import unittest

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from test_control import hand


def world(fist=False):
    _, points = hand()
    if fist:
        for i, x in ((4, .02), (8, -.02), (12, 0), (16, .01), (20, .02)):
            points[i] = P(x=x, y=.04, z=0.)
    return points


def depth(x=.1, y=.2, z=.6):
    return {"points": {"Palm": {"valid": True, "X_m": x, "Y_m": y, "Z_m": z}}}


class UnifiedTests(unittest.TestCase):
    def controller(self):
        from unified_control import UnifiedController
        return UnifiedController(smoothing_ms=0)

    def calibrate(self, controller):
        for i in range(10):
            controller.update(world(), depth(), i * 40)
        self.assertTrue(controller.calibrate_fingers("open"))
        for i in range(10):
            controller.update(world(True), depth(), 400 + i * 40)
        self.assertTrue(controller.calibrate_fingers("fist"))

    def test_finger_calibration_matches_existing_five_value_protocol(self):
        c = self.controller()
        self.calibrate(c)
        closed = c.update(world(True), depth(), 800)
        self.assertEqual(closed["fingers"]["targets_0_180"], [0.] * 5)
        self.assertEqual(closed["fingers"]["serial_preview"], "0,0,0,0,0\n")
        opened = c.update(world(), depth(), 840)
        self.assertEqual(opened["fingers"]["targets_0_180"], [180.] * 5)
        self.assertFalse(opened["hardware_enabled"])

    def test_no_commands_before_calibration_and_no_false_full_open_on_bad_span(self):
        c = self.controller()
        first = c.update(world(), depth(), 0)
        self.assertIsNone(first["fingers"]["targets_0_180"])
        self.assertFalse(c.calibrate_fingers("open"))
        for i in range(1, 11):
            c.update(world(), depth(), i * 40)
        self.assertTrue(c.calibrate_fingers("open"))
        self.assertFalse(c.calibrate_fingers("fist"))
        self.assertIsNone(c.update(world(), depth(), 500)["fingers"]["serial_preview"])

    def test_relative_translation_mapping_and_arm_ik(self):
        c = self.controller()
        c.update(world(), depth(), 0)
        self.assertTrue(c.capture_origin())
        packet = c.update(world(), depth(.11, .19, .58), 40)
        self.assertTrue(packet["arm"]["valid"], packet["arm"])
        np.testing.assert_allclose(packet["arm"]["target_m"], [.258, -.004, .134], atol=1e-8)
        self.assertEqual(len(packet["arm"]["joint_targets_rad"]), 4)
        self.assertTrue(all(abs(a) <= .04 + 1e-8 for a in packet["arm"]["joint_targets_rad"]))

    def test_wrist_neutral_and_signed_twist_are_separate_from_finger_protocol(self):
        from unified_control import palm_frame
        c = self.controller()
        points = world()
        c.update(points, depth(), 0)
        self.assertTrue(c.calibrate_wrist())
        axis = palm_frame(points)[:, 1]
        theta = math.radians(30)
        cross = np.array([[0, -axis[2], axis[1]], [axis[2], 0, -axis[0]], [-axis[1], axis[0], 0]])
        rotation = np.eye(3) * math.cos(theta) + (1 - math.cos(theta)) * np.outer(axis, axis) + math.sin(theta) * cross
        rotated = [P(**dict(zip(("x", "y", "z"), rotation @ np.array([p.x, p.y, p.z])))) for p in points]
        packet = c.update(rotated, depth(), 40)
        self.assertAlmostEqual(packet["wrist"]["twist_rad"], theta)
        self.assertAlmostEqual(packet["wrist"]["servo_preview_deg"], 120)
        self.assertIsNone(packet["fingers"]["serial_preview"])

    def test_loss_nonfinite_reset_and_long_gap_never_emit_stale_targets(self):
        c = self.controller()
        self.calibrate(c)
        c.capture_origin()
        c.calibrate_wrist()
        lost = c.update(None, None, 800)
        for name in ("fingers", "wrist", "arm"):
            self.assertFalse(lost[name]["valid"])
        self.assertIsNone(lost["arm"]["joint_targets_rad"])
        reacquired = c.update(world(), depth(), 2000)
        self.assertFalse(reacquired["arm"]["valid"])
        self.assertFalse(c.capture_origin() is False)
        points = world()
        points[8].x = float("nan")
        bad = c.update(points, depth(), 2040)
        json.dumps(bad, allow_nan=False)
        self.assertFalse(bad["fingers"]["valid"])
        self.assertFalse(bad["arm"]["valid"])
        c.reset()
        reset = c.update(world(), depth(), 2080)
        self.assertIsNone(reset["fingers"]["targets_0_180"])
        self.assertIsNone(reset["arm"]["joint_targets_rad"])

    def test_unreachable_goal_and_stale_timestamp_are_rejected(self):
        c = self.controller()
        c.update(world(), depth(), 0)
        c.capture_origin()
        result = c.update(world(), depth(1., .2, .6), 40)
        self.assertFalse(result["arm"]["valid"])
        self.assertIsNone(result["arm"]["joint_targets_rad"])
        with self.assertRaises(ValueError):
            c.update(world(), depth(), 40)

    def test_finger_calibration_at_sixty_fps(self):
        c = self.controller()
        for i in range(120):
            c.update(world(), depth(), i * 1000 / 60)
        self.assertTrue(c.calibrate_fingers("open"))
        for i in range(120, 240):
            c.update(world(True), depth(), i * 1000 / 60)
        self.assertTrue(c.calibrate_fingers("fist"))

    def test_webcam_wrist_tilt_and_saturation(self):
        c = self.controller()
        c.update(world(), None, 0)
        c.calibrate_wrist()
        p = world()
        for v in p:
            v.x, v.y = -v.y, v.x
        tilted = c.update(p, None, 40)
        self.assertFalse(tilted['wrist']['valid'])
        self.assertFalse(tilted['arm']['valid'])
