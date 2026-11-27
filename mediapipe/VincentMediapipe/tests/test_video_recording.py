from pathlib import Path
import sys
import tempfile
import unittest

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class VideoRecordingTests(unittest.TestCase):
    def test_irregular_frames_keep_elapsed_time_and_last_frame(self):
        from recording import VideoRecorder

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "demo.mp4"
            recorder = VideoRecorder(path, 10, (320, 240))
            try:
                recorder.write(np.zeros((240, 320, 3), np.uint8), 0)
                recorder.write(np.full((240, 320, 3), 100, np.uint8), 100)
                recorder.write(np.full((240, 320, 3), 240, np.uint8), 500)
            finally:
                recorder.close()
            video = cv2.VideoCapture(str(path))
            try:
                self.assertTrue(video.isOpened())
                self.assertEqual(video.get(cv2.CAP_PROP_FRAME_COUNT), 6)
                self.assertAlmostEqual(video.get(cv2.CAP_PROP_FPS), 10)
                frames = []
                while True:
                    ok, frame = video.read()
                    if not ok:
                        break
                    frames.append(frame)
                self.assertLess(frames[0].mean(), 10)
                self.assertGreater(frames[-1].mean(), 220)
            finally:
                video.release()

    def test_existing_video_is_preserved(self):
        from recording import VideoRecorder

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "demo.mp4"
            path.write_bytes(b"existing video")
            with self.assertRaises(FileExistsError):
                VideoRecorder(path, 30, (320, 240))
            self.assertEqual(path.read_bytes(), b"existing video")
