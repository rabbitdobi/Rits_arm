import copy
import math
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class ArmSimulationTests(unittest.TestCase):
    def model(self):
        from arm_simulation import ArmModel
        return ArmModel()

    def test_zero_pose_matches_documented_demo_convention(self):
        model = self.model()
        points = model.forward([0, 0, 0, 0])
        self.assertAlmostEqual(points[1][2], .130)
        self.assertAlmostEqual(points[-1][0], .250)
        self.assertAlmostEqual(points[-1][2], .130)
        self.assertAlmostEqual(points[-1][1], 0)
        self.assertTrue(model.config["simulation_only"])

    def test_fk_ik_roundtrip_for_multiple_valid_targets(self):
        model = self.model()
        for angles in ([0, 0, 0, 0], [.3, .2, -.2, 0], [-.3, .4, -.5, .1]):
            target = model.forward(angles)[-1]
            result = model.solve(target, previous=angles)
            self.assertTrue(result["valid"], result)
            end = model.forward(result["joints_rad"])[-1]
            for a, b in zip(end, target):
                self.assertAlmostEqual(a, b, places=7)
            self.assertAlmostEqual(sum(result["joints_rad"][1:]), 0)

    def test_unreachable_and_outside_workspace_do_not_emit_angles(self):
        model = self.model()
        for target in ([1, 0, .1], [.35, 0, .28], [float("nan"), 0, .1]):
            result = model.solve(target)
            self.assertFalse(result["valid"])
            self.assertIsNone(result["joints_rad"])

    def test_joint_limits_are_rejected_instead_of_silently_clamped(self):
        from arm_simulation import ArmModel
        config = copy.deepcopy(self.model().config)
        config["joint_min_rad"] = [-.001] * 4
        config["joint_max_rad"] = [.001] * 4
        result = ArmModel(config).solve([.25, .03, .13])
        self.assertFalse(result["valid"])
        self.assertEqual(result["reason"], "joint_limits")

    def test_configuration_rejects_bad_geometry_and_nonfinite_values(self):
        from arm_simulation import ArmModel
        for value in (-.1, float("nan")):
            config = copy.deepcopy(self.model().config)
            config["links_m"][0] = value
            with self.assertRaises(ValueError):
                ArmModel(config)
