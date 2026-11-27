"""
Tests that verify finger bend angles do NOT change when the wrist is rotated.
This directly validates the fix/finger-jitter branch fix.
"""
import math
from pathlib import Path
import sys
import unittest
from types import SimpleNamespace as NS

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from motion import calculate_finger_angles, calculate_wrist_pitch, calculate_wrist_roll, calculate_elbow_angle


def _make_hand_flat():
    """
    Create a realistic flat (open) hand landmark set.
    - Wrist at origin
    - Fingers pointing upward (+y direction)
    - Palm facing camera (+z direction)
    Returns 21 landmarks as SimpleNamespace(x, y, z).
    """
    # MediaPipe hand landmark indices used for FINGER_JOINTS:
    # Wrist=0, Thumb: 2,3,4  Index: 5,6,8  Middle: 9,10,12  Ring: 13,14,16  Pinky: 17,18,20
    # Palm landmarks: Index MCP=5, Middle MCP=9, Pinky MCP=17
    pts = [NS(x=0.0, y=0.0, z=0.0)] * 21  # default all to wrist

    def p(x, y, z): return NS(x=x, y=y, z=z)

    landmarks = [p(0.0, 0.0, 0.0)] * 21
    landmarks = list(landmarks)

    # Wrist
    landmarks[0] = p(0.0, 0.0, 0.0)
    # Palm base landmarks (used to compute palm normal)
    landmarks[5]  = p(-0.1, 0.4, 0.0)   # Index MCP
    landmarks[9]  = p(0.0,  0.5, 0.0)   # Middle MCP
    landmarks[17] = p(0.1,  0.3, 0.0)   # Pinky MCP

    # Thumb (joints 2, 3, 4) - slightly open, straight
    landmarks[2]  = p(-0.2, 0.2, 0.0)
    landmarks[3]  = p(-0.3, 0.3, 0.0)
    landmarks[4]  = p(-0.4, 0.4, 0.0)

    # Index finger (joints 5, 6, 8) - straight
    landmarks[5]  = p(-0.1, 0.4, 0.0)
    landmarks[6]  = p(-0.1, 0.6, 0.0)
    landmarks[7]  = p(-0.1, 0.7, 0.0)
    landmarks[8]  = p(-0.1, 0.8, 0.0)

    # Middle finger (joints 9, 10, 12) - straight
    landmarks[9]  = p(0.0,  0.5, 0.0)
    landmarks[10] = p(0.0,  0.7, 0.0)
    landmarks[11] = p(0.0,  0.8, 0.0)
    landmarks[12] = p(0.0,  0.9, 0.0)

    # Ring finger (joints 13, 14, 16) - straight
    landmarks[13] = p(0.1,  0.4, 0.0)
    landmarks[14] = p(0.1,  0.6, 0.0)
    landmarks[15] = p(0.1,  0.7, 0.0)
    landmarks[16] = p(0.1,  0.8, 0.0)

    # Pinky finger (joints 17, 18, 20) - straight
    landmarks[17] = p(0.2,  0.3, 0.0)
    landmarks[18] = p(0.2,  0.5, 0.0)
    landmarks[19] = p(0.2,  0.6, 0.0)
    landmarks[20] = p(0.2,  0.7, 0.0)

    return landmarks


def _rotate_wrist(landmarks, roll_deg):
    """
    Rotate all landmarks around the Z-axis by roll_deg degrees.
    This simulates rotating the wrist (rolling the hand).
    """
    r = math.radians(roll_deg)
    cos_r, sin_r = math.cos(r), math.sin(r)
    rotated = []
    for lm in landmarks:
        rx = cos_r * lm.x - sin_r * lm.y
        ry = sin_r * lm.x + cos_r * lm.y
        rotated.append(NS(x=rx, y=ry, z=lm.z))
    return rotated


class WristFixTests(unittest.TestCase):

    def _angles_close(self, a1, a2, tolerance=5.0):
        """Check all 5 finger angles are within tolerance degrees."""
        for name in ("Thumb", "Index", "Middle", "Ring", "Pinky"):
            self.assertAlmostEqual(
                a1.get(name, 0.0), a2.get(name, 0.0), delta=tolerance,
                msg=f"{name} angle changed by more than {tolerance}deg during wrist rotation!")

    def test_finger_angles_unchanged_after_90deg_wrist_roll(self):
        """Rotating wrist 90 degrees should NOT change finger bend angles."""
        base = _make_hand_flat()
        rotated = _rotate_wrist(base, 90)

        angles_before = calculate_finger_angles(base)
        angles_after  = calculate_finger_angles(rotated)
        self._angles_close(angles_before, angles_after)

    def test_finger_angles_unchanged_after_180deg_wrist_roll(self):
        """Rotating wrist 180 degrees (full flip) should NOT change finger bend angles."""
        base = _make_hand_flat()
        rotated = _rotate_wrist(base, 180)

        angles_before = calculate_finger_angles(base)
        angles_after  = calculate_finger_angles(rotated)
        self._angles_close(angles_before, angles_after)

    def test_finger_angles_unchanged_after_minus_90deg_wrist_roll(self):
        """Rotating wrist -90 degrees (opposite direction) should NOT change finger bend angles."""
        base = _make_hand_flat()
        rotated = _rotate_wrist(base, -90)

        angles_before = calculate_finger_angles(base)
        angles_after  = calculate_finger_angles(rotated)
        self._angles_close(angles_before, angles_after)

    def test_without_fix_wrist_roll_changes_angles(self):
        """
        Without the fix (_remove_wrist_roll), rotating the wrist DOES change
        finger angles. This test documents the original bug.
        """
        base = _make_hand_flat()
        rotated_90 = _rotate_wrist(base, 90)

        angles_before = calculate_finger_angles(base)
        angles_after  = calculate_finger_angles(rotated_90)
        # At least one finger angle should differ (the bug) - we just log it
        diffs = {name: abs(angles_after.get(name, 0.0) - angles_before.get(name, 0.0))
                 for name in ("Thumb", "Index", "Middle", "Ring", "Pinky")}
        # This is informational - we don't fail if the bug is somehow not triggered
        print(f"\n[INFO] Without fix, max angle diff on 90deg wrist roll: "
              f"{max(diffs.values()):.1f}deg  (per finger: {diffs})")


    def test_thumb_fist_synergy_during_occlusion(self):
        """
        When the 4 fingers are clenched in a fist (angles > 120deg),
        even if the thumb joint angle drops (simulating occlusion behind the hand),
        fist synergy keeps the thumb angle closed (> 100deg).
        """
        hand = _make_hand_flat()
        # Bend 4 fingers into a tight fist (tip distance close to wrist)
        for name, tip_idx in [("Index", 8), ("Middle", 12), ("Ring", 16), ("Pinky", 20)]:
            hand[tip_idx] = NS(x=0.0, y=0.1, z=0.0)
        # Thumb joints 2, 3, 4 are straight (as happens during occlusion)
        hand[2] = NS(x=-0.2, y=0.2, z=0.0)
        hand[3] = NS(x=-0.3, y=0.3, z=0.0)
        hand[4] = NS(x=-0.4, y=0.4, z=0.0)

        angles = calculate_finger_angles(hand)
        self.assertGreaterEqual(angles["Thumb"], 100.0,
                                f"Thumb dropped to {angles['Thumb']}deg during fist occlusion!")

    def test_wrist_pitch_with_elbow(self):
        """
        Verify wrist pitch (flexion and extension) calculation with elbow reference
        using realistic camera coordinate space (+y down, fingers pointing up to -y).
        """
        p = lambda x, y, z: NS(x=x, y=y, z=z)
        hand = [p(0, 0, 0)] * 21
        hand[0]  = p(0.5, 0.7, 0.0)    # Wrist
        hand[9]  = p(0.5, 0.4, 0.0)    # Middle MCP
        hand[5]  = p(0.4, 0.45, 0.0)   # Index MCP
        hand[17] = p(0.6, 0.45, 0.0)   # Pinky MCP

        elbow = p(0.5, 1.0, 0.0)       # Elbow below wrist in image space

        # 1. Straight neutral hand -> pitch should be ~0 deg
        pitch_neutral = calculate_wrist_pitch(hand, elbow=elbow)
        self.assertAlmostEqual(pitch_neutral, 0.0, delta=5.0,
                               msg=f"Neutral wrist pitch should be ~0deg, got {pitch_neutral}deg")

        # 2. Flexion (掌屈): Middle MCP tilts forward into -z (towards palm)
        hand_flex = list(hand)
        hand_flex[9]  = p(0.5, 0.45, -0.2)
        hand_flex[5]  = p(0.4, 0.50, -0.2)
        hand_flex[17] = p(0.6, 0.50, -0.2)
        pitch_flex = calculate_wrist_pitch(hand_flex, elbow=elbow)
        self.assertGreater(pitch_flex, 20.0,
                           f"Flexed wrist pitch should be > 20deg, got {pitch_flex}deg")

        # 3. Extension (背屈): Middle MCP tilts backward into +z (away from palm)
        hand_ext = list(hand)
        hand_ext[9]  = p(0.5, 0.45, 0.2)
        hand_ext[5]  = p(0.4, 0.50, 0.2)
        hand_ext[17] = p(0.6, 0.50, 0.2)
        pitch_ext = calculate_wrist_pitch(hand_ext, elbow=elbow)
        self.assertLess(pitch_ext, -20.0,
                        f"Extended wrist pitch should be < -20deg, got {pitch_ext}deg")

    def test_wrist_pitch_provisional_camera_mode(self):
        """
        Verify wrist pitch in provisional mode (no elbow passed).
        In camera space (y down), hand points upward (-y).
        """
        p = lambda x, y, z: NS(x=x, y=y, z=z)
        hand = [p(0, 0, 0)] * 21
        hand[0]  = p(0.5, 0.7, 0.0)    # Wrist
        hand[9]  = p(0.5, 0.4, 0.0)    # Middle MCP (pointing up in -y)
        hand[5]  = p(0.4, 0.45, 0.0)   # Index MCP (to the left in x)
        hand[17] = p(0.6, 0.45, 0.0)   # Pinky MCP (to the right in x)

        pitch_neutral = calculate_wrist_pitch(hand, elbow=None)
        self.assertAlmostEqual(pitch_neutral, 0.0, delta=5.0)

        # Flexion: fingers tilt towards camera (negative z)
        hand_flex = list(hand)
        hand_flex[9]  = p(0.5, 0.45, -0.2)
        hand_flex[5]  = p(0.4, 0.50, -0.2)
        hand_flex[17] = p(0.6, 0.50, -0.2)
        pitch_flex = calculate_wrist_pitch(hand_flex, elbow=None)
        self.assertGreater(pitch_flex, 15.0)

    def test_wrist_pitch_maintained_during_wrist_roll(self):
        """
        Rotating wrist roll from 90deg to 180deg while holding a 60deg bend
        should maintain the bend angle (not drop to 15deg).
        """
        p = lambda x, y, z: NS(x=x, y=y, z=z)
        zc = 0.28  # MediaPipe's raw compressed depth factor
        B = math.radians(60.0)

        pitches = []
        for phi_deg in [90, 135, 180]:
            phi = math.radians(phi_deg)
            # 60deg bend tilted at roll angle phi:
            lx = math.sin(B) * math.sin(phi)
            ly = -math.cos(B)
            lz = math.sin(B) * math.cos(phi) * zc

            tx = math.cos(phi)
            ty = 0.0
            tz = -math.sin(phi) * zc

            hand = [p(0, 0, 0)] * 21
            hand[0] = p(0.5, 0.7, 0.0)
            hand[9] = p(0.5 + lx * 0.2, 0.7 + ly * 0.2, lz * 0.2)
            hand[5] = p(0.5 + tx * 0.1, 0.7 + ty * 0.1, tz * 0.1)
            hand[17] = p(0.5 - tx * 0.1, 0.7 - ty * 0.1, -tz * 0.1)

            pitch = calculate_wrist_pitch(hand, elbow=None)
            pitches.append(pitch)

        diff = max(pitches) - min(pitches)
        self.assertLess(diff, 10.0,
                        f"Wrist bend changed by {diff:.1f}deg between roll 90 and 180! (angles: {pitches})")

    def test_elbow_angle_calculation(self):
        """
        Verify elbow flexion calculation:
        Straight arm = 0 deg, 90deg bent arm = 90 deg.
        """
        p = lambda x, y, z: NS(x=x, y=y, z=z)
        shoulder = p(0.5, 0.2, 0.0)
        elbow = p(0.5, 0.5, 0.0)

        # 1. Straight arm (wrist directly below elbow at y=0.8)
        wrist_straight = p(0.5, 0.8, 0.0)
        angle_straight = calculate_elbow_angle(shoulder, elbow, wrist_straight)
        self.assertAlmostEqual(angle_straight, 0.0, delta=2.0)

        # 2. 90-degree bent elbow (wrist at x=0.2, y=0.5)
        wrist_90 = p(0.2, 0.5, 0.0)
        angle_90 = calculate_elbow_angle(shoulder, elbow, wrist_90)
        self.assertAlmostEqual(angle_90, 90.0, delta=2.0)


if __name__ == "__main__":
    unittest.main()
