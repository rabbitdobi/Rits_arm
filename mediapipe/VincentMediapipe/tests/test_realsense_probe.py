from pathlib import Path
import sys
import unittest

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class DepthProbeTests(unittest.TestCase):
    def test_raw_units_use_device_scale_and_reject_holes(self):
        from realsense_probe import depth_summary
        image = np.full((100, 100), 800, np.uint16)
        result = depth_summary(image, .001)
        self.assertAlmostEqual(result["center_m"], .8)
        image[47:53, 47:53] = 0
        result = depth_summary(image, .001)
        self.assertIsNone(result["center_m"])
        self.assertEqual(result["center_valid_fraction"], 0)
        self.assertGreater(result["valid_fraction"], .99)

    def test_scale_is_not_assumed_to_be_millimeters(self):
        from realsense_probe import depth_summary
        result = depth_summary(np.full((100, 100), 4000, np.uint16), .0001)
        self.assertAlmostEqual(result["center_m"], .4)

    def test_mostly_missing_patch_does_not_use_a_single_good_pixel(self):
        from realsense_probe import depth_summary
        image = np.zeros((100, 100), np.uint16)
        image[50, 50] = 600
        self.assertIsNone(depth_summary(image, .001)["center_m"])
