from pathlib import Path
import csv
import json
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "mediapipe" / "main.py"


class CliTests(unittest.TestCase):
    def test_headless_video_exports_every_lost_frame_with_video_timestamps(self):
        import cv2
        import numpy as np

        with tempfile.TemporaryDirectory() as directory:
            video_path = Path(directory) / "blank.avi"
            csv_path = Path(directory) / "motion.csv"
            video = cv2.VideoWriter(str(video_path), cv2.VideoWriter_fourcc(*"MJPG"),
                                    25, (320, 240))
            self.assertTrue(video.isOpened(), "Test environment needs MJPG video encoding")
            try:
                for _ in range(4):
                    video.write(np.zeros((240, 320, 3), dtype=np.uint8))
            finally:
                video.release()
            result = subprocess.run([sys.executable, str(SCRIPT), "--video", str(video_path),
                                     "--headless", "--json", "--csv", str(csv_path)],
                                    cwd=directory, capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stderr)
            frames = [json.loads(line) for line in result.stdout.splitlines()]
            self.assertEqual([f["timestamp_ms"] for f in frames], [0, 40, 80, 120])
            self.assertTrue(all(not f["tracked"] and f["fingers"] == {} for f in frames))
            with csv_path.open(newline="") as recording:
                rows = list(csv.DictReader(recording))
            self.assertEqual(len(rows), 4)
            self.assertEqual([row["timestamp_ms"] for row in rows], ["0", "40", "80", "120"])
            self.assertTrue(all(row["speed"] == "" and row["x"] == "" for row in rows))

    def test_help_works_from_another_directory_without_opening_camera(self):
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run([sys.executable, str(SCRIPT), "--help"],
                                    cwd=directory, capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--json", result.stdout)
        self.assertIn("--camera", result.stdout)

    def test_existing_recording_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "recording.csv"
            path.write_text("existing recording")
            result = subprocess.run([sys.executable, str(SCRIPT), "--csv", str(path),
                                     "--headless"], capture_output=True, text=True, timeout=20)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(path.read_text(), "existing recording")
            self.assertIn("already exists", result.stderr)


if __name__ == "__main__":
    unittest.main()
