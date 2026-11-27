"""Save annotated frames at a constant rate while preserving elapsed time."""

from pathlib import Path

import cv2


class VideoRecorder:
    def __init__(self, path, fps, size):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # Reserve the name exclusively before OpenCV opens the output.
        with self.path.open("xb"):
            pass
        self.writer = cv2.VideoWriter(
            str(self.path), cv2.VideoWriter_fourcc(*"mp4v"), fps, size)
        if not self.writer.isOpened():
            self.writer.release()
            self.path.unlink(missing_ok=True)
            raise RuntimeError(f"Could not open MP4 encoder: {self.path}")
        self.fps = fps
        self.count = 0
        self.previous = None

    def write(self, frame, timestamp_ms):
        target = round(timestamp_ms * self.fps / 1000)
        # Hold the previous image across slow camera/inference frames.
        while self.count < target:
            self.writer.write(self.previous if self.previous is not None else frame)
            self.count += 1
        if self.count == target:
            self.writer.write(frame)
            self.count += 1
        self.previous = frame.copy()

    def close(self):
        self.writer.release()
