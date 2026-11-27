from pathlib import Path
import sys
import unittest
from unittest.mock import Mock

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from linux_teleop import AXES, JOINTS, LiveControl, LocalMapping, TEACH_M


def make_mapping():
    deltas = ([80, 0, 0, 0], [0, 85, -20, 15], [0, 15, 85, -20])
    poses = {"neutral": {str(m): 2048 for m in JOINTS}}
    for index, name in enumerate(AXES):
        sign = 1 if index % 2 == 0 else -1
        poses[name] = {str(m): 2048 + sign * delta
                       for m, delta in zip(JOINTS, deltas[index // 2])}
    limits = {m: (1900, 2200) for m in JOINTS}
    return LocalMapping(poses, limits), limits


class LinuxTeleopTests(unittest.TestCase):
    def test_mapping_reaches_taught_endpoint_at_bounded_speed(self):
        mapping, _ = make_mapping()
        offset = np.zeros(3)
        previous = mapping.neutral
        desired = mapping.project([10, 0, 0])
        for _ in range(100):
            offset, goal = mapping.step(offset, desired, previous)
            self.assertLessEqual(max(abs(goal[m] - previous[m]) for m in JOINTS), 3)
            self.assertLessEqual(np.abs(offset).sum(), TEACH_M + 1e-9)
            previous = goal
        self.assertEqual(previous, {1: 2128, 2: 2048, 3: 2048, 4: 2048})

    def test_depth_loss_latches_and_reengagement_reanchors(self):
        mapping, limits = make_mapping()
        bus = Mock()
        position = mapping.neutral.copy()
        bus.enable.return_value = position.copy()
        bus.positions.side_effect = position.copy
        bus.send_pose.side_effect = position.update
        live = LiveControl(bus, limits, mapping, None)

        def frame(index, x=0.0, valid=True, key=-1):
            data = dict(tracked=True, depth={"color_frame_number": index, "points": {
                "Palm": dict(valid=valid, X_m=x, Y_m=0, Z_m=.75)}})
            live.frame(data, key, index * .04, index * .04 + .01)

        for i in range(8):
            frame(i)
        self.assertFalse(bus.enable.called)
        frame(8, key=ord("g"))
        for i in range(9, 16):
            frame(i, x=.02)
        self.assertTrue(bus.send_pose.called)
        count = bus.send_pose.call_count
        frame(16, valid=False)
        self.assertFalse(live.active)
        for i in range(17, 33):
            frame(i, x=.09, key=ord("g") if i == 28 else -1)
        self.assertTrue(live.active)
        self.assertEqual(bus.send_pose.call_count, count)
        bus.enable.assert_called_once()
        frame(50, x=.09)
        self.assertFalse(live.active)

    def test_hand_requires_engage_and_sends_bounded_five_value_packet(self):
        hand = Mock(in_waiting=0)
        hand.write.side_effect = len
        live = LiveControl(None, None, None, hand)
        ready = {"targets": {"fingers": {"valid": True, "targets_0_180": [0] * 5}}}
        live.frame(ready, -1, 0.0, .01)
        self.assertFalse(hand.write.called)
        live.frame(ready, ord("g"), .04, .05)
        live.frame(ready, -1, .16, .17)
        hand.write.assert_called_once_with(b"172,172,172,172,172\n")
        live.frame({}, -1, .28, .29)
        self.assertFalse(live.active)
        live.frame(ready, -1, .4, .41)
        self.assertEqual(hand.write.call_count, 1)
