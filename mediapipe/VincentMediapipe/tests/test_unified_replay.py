import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest

import cv2
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from unified_replay import run


class ReplayTests(unittest.TestCase):
    def test_dense_recorded_samples_all_render_and_keep_measurement_timestamps(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            samples = root / 'samples'
            samples.mkdir()
            timestamps = [0, 100, 200]
            for i,t in enumerate(timestamps):
                stem = samples / f'{i:06}'
                stem.with_suffix('.json').write_text(json.dumps(dict(timestamp_ms=t, depth={'points':{}})))
                np.savez(stem.with_suffix('.npz'), color_bgr=np.zeros((480,640,3),dtype=np.uint8))
            output = root/'replay'
            with contextlib.redirect_stdout(io.StringIO()):
                run(SimpleNamespace(samples=samples, output=output))
            packets = [json.loads(line) for line in (output/'targets.jsonl').read_text().splitlines()]
            self.assertEqual([p['timestamp_ms'] for p in packets], timestamps)
            capture = cv2.VideoCapture(str(output/'preview.mp4'))
            try:
                self.assertTrue(capture.isOpened())
                self.assertEqual(capture.get(cv2.CAP_PROP_FRAME_COUNT), len(timestamps))
                self.assertEqual(capture.get(cv2.CAP_PROP_FPS), 1)
            finally:
                capture.release()
