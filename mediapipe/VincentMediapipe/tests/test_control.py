import json
import math
from pathlib import Path
import sys
from types import SimpleNamespace as P
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def hand(scale=1):
    world = [P(x=0., y=0., z=0.) for _ in range(21)]
    world[0] = P(x=0., y=0., z=0.)
    for ids, x, y in [((5, 6, 7, 8), -.04, .05),
                       ((9, 10, 11, 12), 0., .06),
                       ((13, 14, 15, 16), .02, .055),
                       ((17, 18, 19, 20), .04, .05)]:
        for offset, i in enumerate(ids):
            world[i] = P(x=x, y=y + offset * .02, z=0.)
    for offset, i in enumerate((1, 2, 3, 4)):
        world[i] = P(x=-.03 - offset * .02, y=.01 + offset * .01, z=0.)
    image = [P(x=.5 + p.x * 3 * scale, y=.7 - p.y * 3 * scale, z=0.) for p in world]
    return image, world


def calibrate(tracker):
    tracker.request_calibration()
    for i in range(20):
        result = tracker.update(*hand(), i * 50, (640, 480))
    return result


class ControlTests(unittest.TestCase):
    def tracker(self):
        from control import ControlTracker
        return ControlTracker(40, smoothing_ms=0)

    def test_known_distance_inverse_scale_and_reset(self):
        tracker = self.tracker()
        self.assertIsNone(tracker.update(*hand(), 0, (640, 480))["distance_cm"])
        tracker = self.tracker()
        baseline = calibrate(tracker)
        self.assertEqual(baseline["status"], "estimated")
        self.assertAlmostEqual(baseline["distance_cm"], 40)
        measured = tracker.update(*hand(.8), 1000, (640, 480))
        self.assertAlmostEqual(measured["distance_cm"], 50)
        self.assertAlmostEqual(measured["delta_cm"], 10)
        self.assertEqual(measured["calibration"]["reference_cm"], 40)
        tracker.reset()
        self.assertIsNone(tracker.update(*hand(), 1050, (640, 480))["distance_cm"])

    def test_world_geometry_flexion_is_scale_independent(self):
        tracker = self.tracker()
        straight = tracker.update(*hand(), 0, (640, 480))
        self.assertAlmostEqual(straight["flexion"]["Index"], 0)
        image, world = hand()
        world[7] = P(x=-.02, y=.07, z=0.)
        world[8] = P(x=-.02, y=.05, z=0.)
        bent = tracker.update(image, world, 50, (640, 480))
        self.assertAlmostEqual(bent["flexion"]["Index"], 1)
        for p in world:
            p.x *= 2
            p.y *= 2
        self.assertAlmostEqual(tracker.update(image, world, 100, (640, 480))["flexion"]["Index"], 1)

    def test_lost_tilted_invalid_and_changed_resolution_have_no_depth(self):
        tracker = self.tracker()
        calibrate(tracker)
        lost = tracker.update(None, None, 1000, (640, 480))
        self.assertIsNone(lost["distance_cm"])
        self.assertEqual(lost["flexion"], {})
        image, world = hand()
        # Rotate the palm 60 degrees about its vertical axis.
        for p in world:
            p.x, p.z = p.x * .5, p.x * math.sqrt(3) / 2
        self.assertIsNone(tracker.update(image, world, 1050, (640, 480))["distance_cm"])
        image, world = hand()
        world[8].x = float("nan")
        invalid = tracker.update(image, world, 1100, (640, 480))
        self.assertIsNone(invalid["distance_cm"])
        json.dumps(invalid, allow_nan=False)
        self.assertIsNone(tracker.update(*hand(), 1150, (1280, 720))["distance_cm"])

    def test_span_disagreement_and_degenerate_geometry_rejected(self):
        tracker = self.tracker()
        calibrate(tracker)
        image, world = hand()
        image[17].x = image[5].x + .05
        self.assertIsNone(tracker.update(image, world, 1000, (640, 480))["distance_cm"])
        image, world = hand()
        world[5] = world[0]
        self.assertIsNone(tracker.update(image, world, 1050, (640, 480))["distance_cm"])

    def test_unstable_calibration_is_not_accepted_and_loss_restarts_collection(self):
        tracker = self.tracker()
        tracker.request_calibration()
        for i in range(20):
            result = tracker.update(*hand(1 if i % 2 else .6), i * 50, (640, 480))
        self.assertIsNone(result["distance_cm"])
        self.assertNotEqual(result["status"], "estimated")
        tracker.update(None, None, 1000, (640, 480))
        result = tracker.update(*hand(), 1050, (640, 480))
        self.assertLess(result["calibration_samples"], 20)

    def test_gap_does_not_smooth_new_distance_from_stale_position(self):
        from control import ControlTracker
        tracker = ControlTracker(40)
        calibrate(tracker)
        self.assertAlmostEqual(tracker.update(*hand(.5), 2000, (640, 480))["distance_cm"], 80)

    def test_reference_must_be_positive_and_finite(self):
        from control import ControlTracker
        for value in (0, -1, float("nan"), float("inf")):
            with self.assertRaises(ValueError):
                ControlTracker(value)

    def test_derived_overflow_never_becomes_a_depth_measurement(self):
        from control import ControlTracker
        tracker = ControlTracker(1e308, smoothing_ms=0)
        calibrate(tracker)
        result = tracker.update(*hand(.5), 1000, (640, 480))
        self.assertIsNone(result["distance_cm"])
        self.assertIsNone(result["delta_cm"])
        json.dumps(result, allow_nan=False)
