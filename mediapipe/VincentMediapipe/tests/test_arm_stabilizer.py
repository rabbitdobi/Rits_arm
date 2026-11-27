from pathlib import Path
import sys
import copy
import math
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))


def point(x=0.,source='pose',valid=True):
    return dict(valid=valid,visible=True,X_m=x if valid else None,Y_m=0. if valid else None,Z_m=1. if valid else None,
                image_x=.5+x*.1,image_y=.5,landmark_source=source,reason='ok' if valid else 'center_hole')


class StabilizerTests(unittest.TestCase):
    def tracker(self,ms=80):
        from arm_stabilizer import ArmStabilizer
        return ArmStabilizer(smoothing_ms=ms)

    def test_source_switch_is_smaller_than_raw_step_and_eventually_converges(self):
        c=self.tracker();c.update({'Right_Wrist':point()},0)
        points={'Right_Wrist':point(.03,'hand_wrist')};saved=copy.deepcopy(points)
        filtered=c.update(points,40)['points']['Right_Wrist']
        self.assertLess(filtered['X_m'],.008)
        self.assertTrue(filtered['stabilization']['source_changed'])
        self.assertEqual(points,saved)
        for t in range(80,1040,40):last=c.update(points,t)['points']['Right_Wrist']
        self.assertAlmostEqual(last['X_m'],.03,places=5)

    def test_loss_gap_and_nonfinite_never_reuse_old_position(self):
        c=self.tracker();c.update({'Right_Wrist':point()},0)
        lost=c.update({'Right_Wrist':point(valid=False)},40)['points']['Right_Wrist']
        self.assertFalse(lost['valid']);self.assertIsNone(lost['X_m'])
        fresh=c.update({'Right_Wrist':point(.2)},80)['points']['Right_Wrist']
        self.assertEqual(fresh['X_m'],.2)
        later=c.update({'Right_Wrist':point(.4)},1000)['points']['Right_Wrist']
        self.assertEqual(later['X_m'],.4)
        bad=c.update({'Right_Wrist':point(float('nan'))},1040)['points']['Right_Wrist']
        self.assertFalse(bad['valid']);self.assertIsNone(bad['X_m'])

    def test_elapsed_time_not_frame_count_controls_smoothing(self):
        results=[]
        for step in (10,20,40):
            c=self.tracker();c.update({'Wrist':point()},0)
            for t in range(step,401,step):r=c.update({'Wrist':point(.1)},t)
            results.append(r['points']['Wrist']['X_m'])
        for value in results:self.assertAlmostEqual(value,.1*(1-math.exp(-.4/.08)))

    def test_disabled_filter_and_invalid_settings_or_timestamps(self):
        c=self.tracker(0);c.update({'Wrist':point()},0)
        r=c.update({'Wrist':point(.03,'hand_wrist')},40)
        self.assertEqual(r['points']['Wrist']['X_m'],.03)
        with self.assertRaises(ValueError):c.update({'Wrist':point()},40)
        for value in (-1,float('nan'),float('inf')):
            with self.assertRaises(ValueError):self.tracker(value)

    def test_real_movement_settles_without_changing_raw_measurement(self):
        c=self.tracker();c.update({'Wrist':point()},0)
        for t in range(40,441,40):r=c.update({'Wrist':point(.2)},t)
        self.assertLess(abs(r['points']['Wrist']['X_m']-.2),.001)

    def test_filtered_output_does_not_change_raw_geometry_or_fill_rejected_arm(self):
        from human_arm import HumanArmTracker
        from test_human_arm import pose,project
        import numpy as np
        c=HumanArmTracker()
        raw=np.full((100,100),1000)
        first=c.update(pose(),0,raw,.001,project)
        saved=copy.deepcopy(first['points'])
        pts=pose();pts[16].x=.61
        second=c.update(pts,40,raw,.001,project)
        self.assertAlmostEqual(second['points']['Right_Wrist']['X_m'],.61)
        self.assertLess(second['stabilized']['points']['Right_Wrist']['X_m'],.61)
        self.assertEqual(first['points'],saved)
        raw[29:32,59:62]=3000
        rejected=c.update(pose(),80,raw,.001,project)
        self.assertFalse(rejected['arms']['Right']['valid'])
        self.assertFalse(rejected['stabilized']['arms']['Right']['valid'])
        self.assertIsNone(rejected['stabilized']['points']['Right_Wrist']['X_m'])
