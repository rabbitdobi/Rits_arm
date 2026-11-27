from pathlib import Path
import sys
import unittest
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from human_arm import HumanArmTracker
from test_human_arm import pose

class ArmViewTests(unittest.TestCase):
    def test_overlay_mirrors_image_points_without_changing_measurements(self):
        from human_arm_view import draw_human_arm_overlay,draw_human_arm_depth
        r=HumanArmTracker().update(pose(),0)
        image=np.zeros((480,640,3),dtype=np.uint8)
        draw_human_arm_overlay(image,r,30)
        x,y=int((1-.3)*639),int(.3*479)
        self.assertGreater(image[y,x].max(),0)
        self.assertEqual(r['points']['Right_Shoulder']['image_x'],.3)
        draw_human_arm_depth(image,r)
        self.assertGreater(image.max(),100)

    def test_small_preview_and_lost_frame_render(self):
        from human_arm_view import draw_human_arm_depth
        image=np.zeros((240,320,3),dtype=np.uint8)
        draw_human_arm_depth(image,HumanArmTracker().update(None,0))
        self.assertEqual(image.shape,(240,320,3))
