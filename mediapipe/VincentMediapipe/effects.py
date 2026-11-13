"""Time-fading fingertip trails; visualization never changes motion data."""

from collections import deque

import cv2
import numpy as np

COLORS = {"Thumb": (80, 160, 255), "Index": (255, 230, 60),
          "Middle": (190, 80, 255), "Ring": (80, 255, 160),
          "Pinky": (255, 100, 160)}  # OpenCV BGR
CONNECTIONS = [(0, 1), (1, 2), (2, 3), (3, 4),
               (0, 5), (5, 6), (6, 7), (7, 8),
               (5, 9), (9, 10), (10, 11), (11, 12),
               (9, 13), (13, 14), (14, 15), (15, 16),
               (13, 17), (0, 17), (17, 18), (18, 19), (19, 20)]


class FingerTrails:
    def __init__(self, lifetime_ms=600):
        self.lifetime_ms = lifetime_ms
        self.points = {name: deque(maxlen=240) for name in COLORS}
        self.last_timestamp = None

    def update(self, frame):
        timestamp = frame["timestamp_ms"]
        if (not frame["tracked"] or
                (self.last_timestamp is not None and timestamp - self.last_timestamp > 250)):
            for points in self.points.values():
                points.clear()
        self.last_timestamp = timestamp
        for name, finger in frame["fingers"].items():
            self.points[name].append((timestamp, finger["x"], finger["y"]))

    def draw(self, image, timestamp_ms):
        height, width = image.shape[:2]
        ink = np.zeros_like(image)
        for name, points in self.points.items():
            while points and timestamp_ms - points[0][0] >= self.lifetime_ms:
                points.popleft()
            for old, new in zip(points, list(points)[1:]):
                fade = max(0.0, 1 - (timestamp_ms - old[0]) / self.lifetime_ms)
                color = tuple(int(value * fade) for value in COLORS[name])
                a = (int(old[1] * (width - 1)), int(old[2] * (height - 1)))
                b = (int(new[1] * (width - 1)), int(new[2] * (height - 1)))
                cv2.line(ink, a, b, color, max(1, int(4 * fade)), cv2.LINE_AA)
        glow = cv2.GaussianBlur(ink, (0, 0), 7)
        cv2.addWeighted(image, 1, glow, 1.4, 0, dst=image)
        cv2.addWeighted(image, 1, ink, 0.9, 0, dst=image)


def draw_tracking(image, landmarks, frame, fps):
    height, width = image.shape[:2]
    if landmarks is not None:
        points = [(int((1 - lm.x) * (width - 1)), int(lm.y * (height - 1)))
                  for lm in landmarks]
        for a, b in CONNECTIONS:
            cv2.line(image, points[a], points[b], (130, 170, 140), 1, cv2.LINE_AA)
        for point in points:
            cv2.circle(image, point, 3, (210, 240, 220), -1, cv2.LINE_AA)
        for name, finger in frame["fingers"].items():
            point = (int(finger["x"] * (width - 1)), int(finger["y"] * (height - 1)))
            cv2.circle(image, point, 7, COLORS[name], -1, cv2.LINE_AA)
            cv2.circle(image, point, 3, (255, 255, 255), -1, cv2.LINE_AA)
    panel_height, panel_width = min(height, 190), min(width, 580)
    panel = image[:panel_height, :panel_width]
    cv2.addWeighted(panel, 0.25, np.zeros_like(panel), 0.75, 0, dst=panel)
    status = "RIGHT HAND" if frame["tracked"] else "RIGHT HAND LOST - show your right hand"
    cv2.putText(image, f"{status} | {fps:.0f} FPS", (12, 23),
                cv2.FONT_HERSHEY_SIMPLEX, 0.53, (220, 255, 230), 1, cv2.LINE_AA)
    for row, (name, finger) in enumerate(frame["fingers"].items()):
        speed = "--" if finger["speed"] is None else f"{finger['speed']:.2f}"
        angle = finger.get("angle", 0.0)
        label = f"{name:6s}  bend {angle:4.0f}deg  x {finger['x']:.2f}  y {finger['y']:.2f}  spd {speed}/s"
        cv2.putText(image, label, (12, 47 + row * 23), cv2.FONT_HERSHEY_SIMPLEX,
                    0.46, COLORS[name], 1, cv2.LINE_AA)
    wrist = frame.get("wrist_angle", 0.0)
    cv2.putText(image, f"Wrist   roll {wrist:4.0f}deg  (0=palm, 90=side, 180=back)",
                (12, 47 + 5 * 23), cv2.FONT_HERSHEY_SIMPLEX, 0.46, (220, 220, 255), 1, cv2.LINE_AA)
