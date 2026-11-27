import csv
import io
import json
from pathlib import Path
import sys
from types import SimpleNamespace as P
import unittest
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def pose():
    pts=[P(x=.5,y=.5,z=0.,visibility=.99,presence=.99) for _ in range(33)]
    for i,x,y in ((12,.3,.3),(14,.6,.3),(16,.6,.6),(11,.7,.3),(13,.8,.4),(15,.8,.6)):
        pts[i]=P(x=x,y=y,z=0.,visibility=.99,presence=.99)
    return pts


def project(pixel,z):
    return [pixel[0]/100*z,pixel[1]/100*z,z]


class HumanArmTests(unittest.TestCase):
    def tracker(self):
        from human_arm import HumanArmTracker
        return HumanArmTracker()

    def test_metric_right_arm_known_lengths_elbow_and_relative_position(self):
        c=self.tracker()
        r=c.update(pose(),0,np.full((100,100),1000,dtype=np.uint16),.001,project)
        right=r['arms']['Right']
        self.assertTrue(right['valid'],right)
        self.assertAlmostEqual(right['upper_arm_m'],.3)
        self.assertAlmostEqual(right['forearm_m'],.3)
        self.assertAlmostEqual(right['elbow_flexion_deg'],90.)
        np.testing.assert_allclose(right['wrist_relative_shoulder_m'],[.3,.3,0])
        self.assertEqual(r['coordinate_frame'],'d455_color_optical')
        self.assertAlmostEqual(r['points']['Right_Shoulder']['X_m'],.3)

    def test_straight_arm_is_zero_flexion(self):
        pts=pose();pts[16].x=.9;pts[16].y=.3
        r=self.tracker().update(pts,0,np.full((100,100),1000),.001,project)
        self.assertAlmostEqual(r['arms']['Right']['elbow_flexion_deg'],0)

    def test_confidence_hole_and_loss_do_not_reuse_values(self):
        c=self.tracker(); raw=np.full((100,100),1000)
        c.update(pose(),0,raw,.001,project)
        pts=pose();pts[14].visibility=.1
        low=c.update(pts,40,raw,.001,project)
        self.assertFalse(low['points']['Right_Elbow']['visible'])
        self.assertIsNone(low['points']['Right_Elbow']['X_m'])
        self.assertIsNone(low['arms']['Right']['elbow_flexion_deg'])
        raw[30,60]=0
        hole=c.update(pose(),80,raw,.001,project)
        self.assertEqual(hole['points']['Right_Elbow']['reason'],'center_hole')
        lost=c.update(None,120,raw,.001,project)
        self.assertTrue(all(not p['valid'] for p in lost['points'].values()))
        self.assertFalse(lost['arms']['Right']['valid'])
        json.dumps(lost,allow_nan=False)

    def test_video_without_depth_is_only_two_dimensional(self):
        r=self.tracker().update(pose(),0)
        self.assertTrue(r['points']['Right_Elbow']['visible'])
        self.assertIsNone(r['points']['Right_Elbow']['Z_m'])
        self.assertFalse(r['arms']['Right']['valid'])

    def test_nonfinite_out_of_frame_and_background_depth_not_valid_geometry(self):
        for value in (float('nan'),-1,1):
            p=pose();p[14].x=value
            r=self.tracker().update(p,0,np.full((100,100),1000),.001,project)
            self.assertFalse(r['points']['Right_Elbow']['visible'])
            json.dumps(r,allow_nan=False)
        raw=np.full((100,100),1000);raw[29:32,59:62]=3000
        r=self.tracker().update(pose(),0,raw,.001,project)
        self.assertFalse(r['arms']['Right']['valid'])
        self.assertEqual(r['arms']['Right']['reason'],'implausible_segment_length')

    def test_largest_visible_person_is_selected(self):
        from human_arm import select_pose
        a=pose(); b=pose()
        for p in b:
            p.x=.5+(p.x-.5)*.25;p.y=.5+(p.y-.5)*.25
        self.assertEqual(select_pose(P(pose_landmarks=[b,a])),1)
        self.assertIsNone(select_pose(P(pose_landmarks=[])))

    def test_csv_records_six_current_joints_and_rejects_duplicate_time(self):
        from human_arm import HUMAN_ARM_FIELDS,write_human_arm_csv
        c=self.tracker();r=c.update(None,0)
        f=io.StringIO();w=csv.DictWriter(f,fieldnames=HUMAN_ARM_FIELDS);w.writeheader()
        write_human_arm_csv(w,r)
        rows=list(csv.DictReader(io.StringIO(f.getvalue())))
        self.assertEqual(len(rows),6)
        self.assertTrue(all(row['X_m']=='' for row in rows))
        with self.assertRaises(ValueError):c.update(pose(),0)

    def test_capture_guidance_distinguishes_frame_edge_occlusion_and_depth_hole(self):
        c=self.tracker();p=pose();p[16].x=-.05
        r=c.update(p,0)
        self.assertEqual(r['capture_guidance']['code'],'wrist_out_of_frame')
        self.assertEqual(r['points']['Right_Wrist']['predicted_image_x'],-.05)
        self.assertIsNone(r['points']['Right_Wrist']['X_m'])
        p=pose();p[16].x=.03;p[16].presence=.5
        r=c.update(p,40)
        self.assertEqual(r['capture_guidance']['code'],'wrist_near_edge')
        p=pose();p[16].visibility=.3
        r=c.update(p,80)
        self.assertEqual(r['capture_guidance']['code'],'wrist_occluded')
        raw=np.full((100,100),1000);raw[60,60]=0
        r=c.update(pose(),120,raw,.001,project)
        self.assertEqual(r['capture_guidance']['code'],'wrist_depth_missing')
        r=c.update(pose(),160,np.full((100,100),1000),.001,project)
        self.assertEqual(r['capture_guidance']['code'],'ready')
        p=pose();p[16].x=float('nan')
        json.dumps(c.update(p,200),allow_nan=False)

    def test_matching_hand_wrist_can_support_low_presence_pose_with_real_depth(self):
        c=self.tracker();pts=pose();pts[16].presence=.4
        raw=np.full((100,100),1000)
        hands=[dict(side='Right',score=.95,x=.61,y=.6)]
        r=c.update(pts,0,raw,.001,project,hand_wrists=hands)
        wrist=r['points']['Right_Wrist']
        self.assertTrue(wrist['valid'])
        self.assertEqual(wrist['landmark_source'],'hand_wrist')
        self.assertEqual(wrist['pose_reason'],'low_confidence_or_outside')
        self.assertAlmostEqual(wrist['X_m'],.61)
        self.assertTrue(r['arms']['Right']['valid'])
        self.assertEqual(r['arms']['Right']['hand_assisted_joints'],1)

    def test_hand_assistance_rejects_far_wrong_side_ambiguous_and_missing_depth(self):
        for wrists in (
            [dict(side='Right',score=.95,x=.1,y=.1)],
            [dict(side='Left',score=.95,x=.6,y=.6)],
            [dict(side='Right',score=.5,x=.6,y=.6)],
            [dict(side='Right',score=.95,x=.6,y=.6)]*2,
        ):
            pts=pose();pts[16].presence=.4
            r=self.tracker().update(pts,0,np.full((100,100),1000),.001,project,hand_wrists=wrists)
            self.assertFalse(r['points']['Right_Wrist']['valid'])
        pts=pose();pts[16].presence=.4
        r=self.tracker().update(pts,0,np.zeros((100,100)),.001,project,
            hand_wrists=[dict(side='Right',score=.95,x=.6,y=.6)])
        self.assertFalse(r['points']['Right_Wrist']['valid'])
        r=self.tracker().update(pts,0,hand_wrists=[dict(side='Right',score=.95,x=.6,y=.6)])
        self.assertIsNone(r['points']['Right_Wrist']['Z_m'])

    def test_candidate_audit_is_finite_and_preserves_ambiguity(self):
        pts=pose();pts[16].presence=.4
        candidates=[dict(side='Right',score=.95,x=.6,y=.6)]*2
        candidates += [dict(side='Right',score=float('nan'),x=.6,y=.6)]
        r=self.tracker().update(pts,0,np.full((100,100),1000),.001,project,hand_wrists=candidates)
        self.assertEqual(len(r['hand_wrist_candidates']),2)
        self.assertFalse(r['points']['Right_Wrist']['valid'])
        json.dumps(r,allow_nan=False)

    def test_close_range_hint_is_explicitly_inferred_without_filling_wrist(self):
        raw=np.full((100,100),450)
        raw[60,60]=0
        r=self.tracker().update(pose(),0,raw,.001,project)
        self.assertEqual(r['capture_guidance']['code'],'wrist_may_be_too_close')
        self.assertTrue(r['capture_guidance']['inferred'])
        self.assertIsNone(r['points']['Right_Wrist']['Z_m'])
        self.assertFalse(r['arms']['Right']['valid'])
