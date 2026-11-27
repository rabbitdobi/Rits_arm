import sys
from pathlib import Path
from types import SimpleNamespace
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))


def frame(depth=True,geometry=True):
    return dict(points={'Right_'+j:dict(visible=True,valid=depth) for j in ('Shoulder','Elbow','Wrist')},
                arms={'Right':dict(valid=geometry)})


class ArmQualityTests(unittest.TestCase):
    def quality(self):
        from arm_quality import ArmQuality
        return ArmQuality()

    def test_availability_counts_raw_depth_and_geometry_separately(self):
        q=self.quality()
        for i in range(31):
            result=q.update(frame(depth=i%2==0,geometry=False),i*40)
        self.assertTrue(result['ready'])
        self.assertEqual(result['frames'],31)
        self.assertAlmostEqual(result['depth_complete_percent'],16/31*100)
        self.assertEqual(result['geometry_valid_percent'],0)
        self.assertEqual(result['session']['frames'],31)

    def test_rolling_window_expires_old_samples_without_changing_session_counts(self):
        q=self.quality()
        for i in range(101):
            result=q.update(frame(depth=i>=50,geometry=i>=50),i*40)
        self.assertEqual(result['frames'],50)
        self.assertEqual(result['depth_complete_percent'],100)
        self.assertEqual(result['session']['frames'],101)
        self.assertEqual(result['session']['depth_complete_frames'],51)

    def test_gap_clears_window_and_warmup_never_claims_stability(self):
        q=self.quality()
        first=q.update(frame(),0)
        self.assertFalse(first['ready'])
        self.assertIsNone(first['depth_complete_percent'])
        for i in range(1,31):q.update(frame(),i*40)
        after=q.update(frame(),2000)
        self.assertFalse(after['ready'])
        self.assertIsNone(after['depth_complete_percent'])
        self.assertEqual(after['session']['frames'],32)
        with self.assertRaises(ValueError):q.update(frame(),2000)
