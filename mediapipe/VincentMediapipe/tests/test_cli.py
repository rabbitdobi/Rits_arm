from pathlib import Path
import csv
import json
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "main.py"


class CliTests(unittest.TestCase):
    def test_arm_smoothing_rejects_nonfinite_and_negative_before_camera(self):
        for value in ("nan", "inf", "-1"):
            result = subprocess.run([sys.executable, str(SCRIPT), "--arm-tracking", "--arm-smoothing-ms", value],
                                    capture_output=True, text=True, timeout=20)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("finite and nonnegative", result.stderr)

    def test_depth_samples_require_realsense_and_positive_interval(self):
        for arguments in (["--depth-samples-every", "30"],
                          ["--realsense", "--depth-samples-every", "0"]):
            result = subprocess.run([sys.executable, str(SCRIPT), *arguments],
                                    capture_output=True, text=True, timeout=20)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("error", result.stderr)

    def test_existing_depth_sample_directory_is_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "motion.csv"
            samples = output.with_suffix(".depth-samples")
            samples.mkdir()
            (samples / "existing.txt").write_text("existing data")
            result = subprocess.run([sys.executable, str(SCRIPT), "--realsense",
                                     "--depth-samples-every", "30", "--csv", str(output)],
                                    capture_output=True, text=True, timeout=20)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("already exists", result.stderr)
            self.assertEqual((samples / "existing.txt").read_text(), "existing data")
            self.assertFalse(output.exists())

    def test_realsense_input_is_exclusive_and_frame_limit_is_positive(self):
        for arguments in (["--realsense", "--camera", "0"],
                          ["--realsense", "--video", "example.mp4"],
                          ["--max-frames", "0"], ["--max-frames", "-1"]):
            result = subprocess.run([sys.executable, str(SCRIPT), *arguments],
                                    capture_output=True, text=True, timeout=20)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("error", result.stderr)

    def test_realsense_depth_output_is_preserved_before_device_access(self):
        for suffix in (".depth.csv", ".depth.json"):
            with tempfile.TemporaryDirectory() as directory:
                csv_path = Path(directory) / "motion.csv"
                path = csv_path.with_suffix(suffix)
                path.write_text("existing depth data")
                result = subprocess.run([sys.executable, str(SCRIPT), "--realsense",
                                         "--csv", str(csv_path)],
                                        capture_output=True, text=True, timeout=20)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(path.read_text(), "existing depth data")
                self.assertIn("already exists", result.stderr)
                self.assertFalse(csv_path.exists())

    def test_headless_video_exports_every_lost_frame_with_video_timestamps(self):
        import cv2
        import numpy as np

        with tempfile.TemporaryDirectory() as directory:
            video_path = Path(directory) / "blank.avi"
            csv_path = Path(directory) / "motion.csv"
            recorded_path = Path(directory) / "demo.mp4"
            video = cv2.VideoWriter(str(video_path), cv2.VideoWriter_fourcc(*"MJPG"),
                                    25, (320, 240))
            self.assertTrue(video.isOpened(), "Test environment needs MJPG video encoding")
            try:
                for _ in range(4):
                    video.write(np.zeros((240, 320, 3), dtype=np.uint8))
            finally:
                video.release()
            result = subprocess.run([sys.executable, str(SCRIPT), "--video", str(video_path),
                                     "--headless", "--json", "--csv", str(csv_path),
                                     "--record", str(recorded_path), "--control-preview", "--unified-preview", "--arm-tracking"],
                                    cwd=directory, capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Stop reason: video_end", result.stderr)
            frames = [json.loads(line) for line in result.stdout.splitlines()]
            self.assertEqual([f["timestamp_ms"] for f in frames], [0, 40, 80, 120])
            self.assertTrue(all(not f["tracked"] and f["fingers"] == {} for f in frames))
            self.assertTrue(all(f["control"]["distance_cm"] is None for f in frames))
            controls = [json.loads(line) for line in
                        csv_path.with_suffix(".control.jsonl").read_text().splitlines()]
            self.assertEqual([f["timestamp_ms"] for f in controls], [0, 40, 80, 120])
            self.assertTrue(all(f["status"] == "hand_lost" for f in controls))
            humans = [json.loads(line) for line in csv_path.with_suffix(".human-arm.jsonl").read_text().splitlines()]
            self.assertEqual([p["timestamp_ms"] for p in humans], [0, 40, 80, 120])
            self.assertTrue(all(not p["tracked"] and not p["arms"]["Right"]["valid"] for p in humans))
            self.assertTrue(all(not p["stabilized"]["arms"]["Right"]["valid"] for p in humans))
            self.assertTrue(all(p["stabilized"]["points"]["Right_Wrist"]["X_m"] is None for p in humans))
            with csv_path.with_suffix(".human-arm.csv").open(newline="") as f:
                body_rows = list(csv.DictReader(f))
            self.assertEqual(len(body_rows), 24)
            self.assertTrue(all(p["X_m"] == "" for p in body_rows))
            targets = [json.loads(line) for line in
                       csv_path.with_suffix(".targets.jsonl").read_text().splitlines()]
            self.assertEqual(len(targets), 4)
            self.assertEqual([p["timestamp_ms"] for p in targets], [0, 40, 80, 120])
            for packet in targets:
                self.assertFalse(packet["hardware_enabled"])
                for channel in ("fingers", "wrist", "arm"):
                    self.assertFalse(packet[channel]["valid"])
                self.assertIsNone(packet["arm"]["joint_targets_rad"])
                self.assertIsNone(packet["fingers"]["serial_preview"])
            model = json.loads(csv_path.with_suffix(".targets.config.json").read_text())
            self.assertTrue(model["simulation_only"])
            self.assertFalse(model["geometry_verified"])
            with csv_path.open(newline="") as recording:
                rows = list(csv.DictReader(recording))
            self.assertEqual(len(rows), 4)
            self.assertEqual([row["timestamp_ms"] for row in rows], ["0", "40", "80", "120"])
            self.assertTrue(all(row["speed"] == "" and row["x"] == "" for row in rows))
            replay = cv2.VideoCapture(str(recorded_path))
            try:
                self.assertTrue(replay.isOpened())
                self.assertEqual(replay.get(cv2.CAP_PROP_FRAME_COUNT), 4)
                self.assertAlmostEqual(replay.get(cv2.CAP_PROP_FPS), 25)
                ok, image = replay.read()
                self.assertTrue(ok)
                self.assertEqual(image.shape, (240, 900, 3))
                self.assertGreater(image.max(), 100, "Recorded video must include the overlay")
            finally:
                replay.release()

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

    def test_existing_video_is_rejected_before_opening_camera(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "demo.mp4"
            path.write_bytes(b"existing video")
            result = subprocess.run([sys.executable, str(SCRIPT), "--record", str(path)],
                                    capture_output=True, text=True, timeout=20)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(path.read_bytes(), b"existing video")
            self.assertIn("already exists", result.stderr)

    def test_reference_rejects_invalid_values_before_camera_access(self):
        for value in ("0", "-10", "nan", "inf"):
            result = subprocess.run([sys.executable, str(SCRIPT), "--control-preview",
                                     "--reference-cm", value],
                                    capture_output=True, text=True, timeout=20)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("positive", result.stderr)

    def test_existing_unified_outputs_are_preserved_before_camera_access(self):
        for suffix in (".targets.jsonl", ".targets.config.json", ".human-arm.jsonl", ".human-arm.csv"):
            with tempfile.TemporaryDirectory() as directory:
                output = Path(directory) / "motion.csv"
                path = output.with_suffix(suffix)
                path.write_text("keep existing data")
                result = subprocess.run([sys.executable, str(SCRIPT), "--unified-preview", "--arm-tracking",
                                         "--csv", str(output)], capture_output=True, text=True, timeout=20)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("already exists", result.stderr)
                self.assertEqual(path.read_text(), "keep existing data")
                self.assertFalse(output.exists())

    def test_existing_control_log_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "motion.csv"
            log = path.with_suffix(".control.jsonl")
            log.write_text("existing control log")
            result = subprocess.run([sys.executable, str(SCRIPT), "--control-preview",
                                     "--csv", str(path)],
                                    capture_output=True, text=True, timeout=20)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(log.read_text(), "existing control log")
            self.assertFalse(path.exists())
            self.assertIn("already exists", result.stderr)


if __name__ == "__main__":
    unittest.main()
