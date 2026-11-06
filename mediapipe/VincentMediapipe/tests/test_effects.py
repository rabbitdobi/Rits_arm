from pathlib import Path
import sys
import unittest

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from effects import FingerTrails


def frame(timestamp, x, tracked=True):
    return {"timestamp_ms": timestamp, "tracked": tracked,
            "fingers": {"Index": dict(x=x, y=0.5, speed=1.0)} if tracked else {}}


class TrailTests(unittest.TestCase):
    def test_motion_draws_visible_trail_and_expires_with_time(self):
        trails = FingerTrails(lifetime_ms=600)
        trails.update(frame(0, 0.2))
        trails.update(frame(100, 0.5))
        canvas = np.zeros((100, 200, 3), dtype=np.uint8)
        trails.draw(canvas, 100)
        self.assertGreater(int(canvas[50, 65].sum()), 0)
        empty = np.zeros_like(canvas)
        trails.draw(empty, 701)
        self.assertEqual(int(empty.sum()), 0)

    def test_loss_does_not_connect_old_and_reacquired_fingers(self):
        trails = FingerTrails()
        trails.update(frame(0, 0.2))
        trails.update(frame(100, 0.4))
        trails.update(frame(150, 0, tracked=False))
        trails.update(frame(200, 0.9))
        canvas = np.zeros((100, 200, 3), dtype=np.uint8)
        trails.draw(canvas, 200)
        self.assertEqual(int(canvas[:, :120].sum()), 0)

    def test_large_frame_gap_does_not_draw_a_teleporting_trail(self):
        trails = FingerTrails()
        trails.update(frame(0, 0.2))
        trails.update(frame(300, 0.8))
        canvas = np.zeros((100, 200, 3), dtype=np.uint8)
        trails.draw(canvas, 300)
        self.assertEqual(int(canvas[:, :100].sum()), 0)


if __name__ == "__main__":
    unittest.main()
