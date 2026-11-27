import csv
import io
import json
import tempfile
from pathlib import Path
import sys
from types import SimpleNamespace as P
import unittest

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def deproject(pixel, z):
    # Known pinhole intrinsics: fx=fy=100, cx=cy=50.
    return [(pixel[0] - 50) * z / 100, (pixel[1] - 50) * z / 100, z]


class MetricDepthTests(unittest.TestCase):
    def test_new_output_directories_are_tracked_without_claiming_existing_ones(self):
        from realsense_source import ensure_output_directory
        with tempfile.TemporaryDirectory() as directory:
            existing = Path(directory)
            target = existing / "new" / "nested"
            created = []
            ensure_output_directory(target, created)
            self.assertTrue(target.is_dir())
            self.assertEqual(created, [existing / "new", target])
            ensure_output_directory(target, created)
            self.assertEqual(len(created), 2)
            self.assertNotIn(existing, created)

    def test_unmirrored_pixel_and_device_scale_produce_metric_xyz(self):
        from realsense_source import sample_point
        raw = np.full((100, 100), 4000, np.uint16)
        point = sample_point(raw, .0001, .7, .3, deproject)
        self.assertTrue(point["valid"])
        self.assertEqual((point["pixel_x"], point["pixel_y"]), (70, 30))
        self.assertAlmostEqual(point["X_m"], .08)
        self.assertAlmostEqual(point["Y_m"], -.08)
        self.assertAlmostEqual(point["Z_m"], .4)

    def test_center_hole_is_not_filled_from_neighbors(self):
        from realsense_source import sample_point
        raw = np.full((100, 100), 600, np.uint16)
        raw[50, 50] = 0
        result = sample_point(raw, .001, .5, .5, deproject)
        self.assertFalse(result["valid"])
        self.assertIsNone(result["Z_m"])

    def test_hole_diagnostics_distinguish_isolated_hole_from_empty_patch(self):
        from realsense_source import sample_point
        raw = np.full((100, 100), 600, np.uint16)
        raw[50, 50] = 0
        isolated = sample_point(raw, .001, .5, .5, deproject)
        self.assertAlmostEqual(isolated["valid_fraction"], 8 / 9)
        self.assertAlmostEqual(isolated["spread_m"], 0)
        self.assertFalse(isolated["valid"])
        self.assertIsNone(isolated["Z_m"])
        raw[49:52, 49:52] = 0
        empty = sample_point(raw, .001, .5, .5, deproject)
        self.assertEqual(empty["valid_fraction"], 0)
        self.assertIsNone(empty["spread_m"])

    def test_diagnostic_sample_preserves_unmirrored_color_raw_depth_and_landmarks(self):
        from realsense_source import save_depth_sample
        raw = np.arange(12, dtype=np.uint16).reshape(3, 4)
        color = np.zeros((3, 4, 3), np.uint8)
        color[0, 0] = (1, 2, 3)
        landmarks = [P(x=.2, y=.3, z=.01) for _ in range(21)]
        with tempfile.TemporaryDirectory() as directory:
            created = []
            base = Path(directory)
            native = np.full((2, 2), 5000, np.uint16)
            save_depth_sample(base, 7, raw, color, .0001, landmarks,
                              {"timestamp_ms": 123, "depth": {"points": {}}}, created,
                              native_raw=native)
            with np.load(base / "000007.npz") as data:
                np.testing.assert_array_equal(data["depth_z16"], raw)
                np.testing.assert_array_equal(data["color_bgr"], color)
                self.assertAlmostEqual(float(data["meters_per_unit"]), .0001)
                np.testing.assert_array_equal(data["native_depth_z16"], native)
            metadata = json.loads((base / "000007.json").read_text())
            self.assertEqual(metadata["timestamp_ms"], 123)
            self.assertEqual(metadata["landmarks"][0], dict(x=.2, y=.3, z=.01))
            self.assertEqual(len(created), 2)
            with self.assertRaises(FileExistsError):
                save_depth_sample(base, 7, raw, color, .001, None, {}, created)

    def test_depth_boundary_and_sparse_patch_are_rejected(self):
        from realsense_source import sample_point
        raw = np.full((100, 100), 600, np.uint16)
        raw[:, 51:] = 2000
        self.assertFalse(sample_point(raw, .001, .5, .5, deproject)["valid"])
        raw[:] = 0
        raw[50, 50] = 600
        self.assertFalse(sample_point(raw, .001, .5, .5, deproject)["valid"])

    def test_invalid_landmarks_and_nonfinite_deprojection_remain_null(self):
        from realsense_source import sample_point
        raw = np.full((100, 100), 600, np.uint16)
        for x in (-.01, 1., float("nan"), float("inf")):
            point = sample_point(raw, .001, x, .5, deproject)
            self.assertFalse(point["valid"])
            json.dumps(point, allow_nan=False)
        result = sample_point(raw, .001, .5, .5, lambda pixel, z: [float("nan"), 0, z])
        self.assertFalse(result["valid"])
        self.assertIsNone(result["X_m"])

    def test_all_joints_and_palm_export_loss_without_stale_values(self):
        from realsense_source import metric_hand, write_depth_csv, DEPTH_FIELDS
        raw = np.full((100, 100), 600, np.uint16)
        landmarks = [P(x=.5, y=.5) for _ in range(21)]
        measured = metric_hand(landmarks, raw, .001, deproject)
        self.assertEqual(len(measured["points"]), 22)
        self.assertAlmostEqual(measured["points"]["Palm"]["Z_m"], .6)
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=DEPTH_FIELDS)
        writer.writeheader()
        write_depth_csv(writer, measured, 100, True, .9)
        lost = metric_hand(None, raw, .001, deproject)
        write_depth_csv(writer, lost, 200, False, None)
        rows = list(csv.DictReader(io.StringIO(output.getvalue())))
        self.assertEqual(len(rows), 23)
        self.assertEqual(rows[-1]["reason"], "hand_lost")
        self.assertEqual(rows[-1]["Z_m"], "")
        self.assertEqual(rows[-1]["joint"], "")
