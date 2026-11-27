import sys
from pathlib import Path
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from unified_control import UnifiedController
from unified_view import draw_unified_panel

class ViewTests(unittest.TestCase):
    def test_missing_targets_and_scaled_render(self):
        c = UnifiedController()
        packet = c.update(None, None, 0)
        for h in (480, 720):
            image = draw_unified_panel(packet, c.model, h)
            self.assertEqual(image.shape, (h, 580, 3))
            self.assertGreater(image.max(), image.min())
