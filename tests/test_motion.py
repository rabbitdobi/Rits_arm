import csv
import io
import json
import math
from pathlib import Path
import sys
from types import SimpleNamespace as NS
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "mediapipe"))
from motion import CSV_FIELDS, MotionTracker, select_right_hand, write_csv_frame


def hand(x=0.8, y=0.2):
    return [NS(x=x, y=y, z=0.0) for _ in range(21)]


class MotionTests(unittest.TestCase):
    def test_right_hand_uses_label_and_confidence_not_screen_side(self):
        result = NS(hand_landmarks=[hand(0.1), hand(0.9), hand(0.5)],
                    handedness=[[NS(category_name="Left", score=0.99)],
                                [NS(category_name="Right", score=0.9)],
                                [NS(category_name="Right", score=0.7)]])
        self.assertEqual(select_right_hand(result, 0.6), 1)
        self.assertIsNone(select_right_hand(result, 0.95))
        self.assertIsNone(select_right_hand(NS(hand_landmarks=[], handedness=[]), 0.6))

    def test_first_frame_has_mirrored_position_and_unknown_velocity(self):
        frame = MotionTracker().update(hand(), 0, 0.9)
        self.assertTrue(frame["tracked"])
        self.assertEqual(frame["handedness_score"], 0.9)
        self.assertEqual(set(frame["fingers"]), {"Thumb", "Index", "Middle", "Ring", "Pinky"})
        index = frame["fingers"]["Index"]
        self.assertAlmostEqual(index["x"], 0.2)
        self.assertAlmostEqual(index["y"], 0.2)
        self.assertIsNone(index["speed"])
        self.assertIsNone(index["vx"])

    def test_speed_uses_elapsed_seconds_and_both_axes(self):
        tracker = MotionTracker(smoothing_ms=0)
        tracker.update(hand(0.8, 0.2), 0)
        index = tracker.update(hand(0.5, 0.6), 100)["fingers"]["Index"]
        self.assertAlmostEqual(index["vx"], 3.0)
        self.assertAlmostEqual(index["vy"], 4.0)
        self.assertAlmostEqual(index["speed"], 5.0)

    def test_smoothing_depends_on_time_not_frame_count(self):
        tracker = MotionTracker(smoothing_ms=100)
        tracker.update(hand(0.8), 0)
        first = tracker.update(hand(0.4), 100)["fingers"]["Index"]
        self.assertAlmostEqual(first["x"], 0.2 + 0.4 * (1 - math.exp(-1)))
        second = tracker.update(hand(0.4), 200)["fingers"]["Index"]
        self.assertAlmostEqual(second["x"], 0.6 - 0.4 * math.exp(-2))

    def test_loss_and_long_gap_reset_velocity(self):
        tracker = MotionTracker(smoothing_ms=0)
        tracker.update(hand(), 0)
        lost = tracker.update(None, 100)
        self.assertFalse(lost["tracked"])
        self.assertEqual(lost["fingers"], {})
        self.assertIsNone(lost["handedness_score"])
        self.assertIsNone(tracker.update(hand(0.1), 200)["fingers"]["Thumb"]["speed"])
        self.assertIsNone(tracker.update(hand(0.9), 451)["fingers"]["Thumb"]["speed"])

    def test_non_increasing_timestamps_rejected_without_corrupting_state(self):
        tracker = MotionTracker(smoothing_ms=0)
        tracker.update(hand(), 10)
        for timestamp in (10, 9):
            with self.assertRaises(ValueError):
                tracker.update(hand(0.1), timestamp)
        index = tracker.update(hand(0.7), 110)["fingers"]["Index"]
        self.assertAlmostEqual(index["vx"], 1.0)

    def test_recording_preserves_loss_and_null_speed(self):
        tracker = MotionTracker()
        frame = tracker.update(hand(), 0, 0.9)
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=CSV_FIELDS)
        writer.writeheader()
        write_csv_frame(writer, frame)
        write_csv_frame(writer, tracker.update(None, 100))
        rows = list(csv.DictReader(io.StringIO(output.getvalue())))
        self.assertEqual(len(rows), 6)
        self.assertEqual(rows[0]["finger"], "Thumb")
        self.assertEqual(rows[0]["speed"], "")
        self.assertAlmostEqual(float(rows[0]["x"]), 0.2)
        self.assertEqual(rows[-1]["tracked"], "False")
        self.assertEqual(rows[-1]["finger"], "")
        self.assertEqual(rows[-1]["x"], "")
        parsed = json.loads(json.dumps(frame, allow_nan=False))
        self.assertIsNone(parsed["fingers"]["Thumb"]["speed"])


if __name__ == "__main__":
    unittest.main()
