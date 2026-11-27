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
    panel_height, panel_width = min(height, 166), min(width, 560)
    panel = image[:panel_height, :panel_width]
    cv2.addWeighted(panel, 0.25, np.zeros_like(panel), 0.75, 0, dst=panel)
    status = "RIGHT HAND" if frame["tracked"] else "RIGHT HAND LOST - show your right hand"
    cv2.putText(image, f"{status} | {fps:.0f} FPS", (12, 23),
                cv2.FONT_HERSHEY_SIMPLEX, 0.53, (220, 255, 230), 1, cv2.LINE_AA)
    for row, (name, finger) in enumerate(frame["fingers"].items()):
        speed = "--" if finger["speed"] is None else f"{finger['speed']:.2f}"
        label = f"{name:6s}  x {finger['x']:.3f}  y {finger['y']:.3f}  speed {speed} /s"
        cv2.putText(image, label, (12, 47 + row * 23), cv2.FONT_HERSHEY_SIMPLEX,
                    0.48, COLORS[name], 1, cv2.LINE_AA)


def draw_control(image, control):
    """Five normalized flexion bars and an advisory distance, never servo targets."""
    height, width = image.shape[:2]
    panel_w, panel_h = 470, 310
    scale = min(1., width / panel_w, height / panel_h)
    rendered_w, rendered_h = max(1, int(panel_w * scale)), max(1, int(panel_h * scale))
    target = image[height - rendered_h:, width - rendered_w:]
    image = cv2.resize(target, (panel_w, panel_h))
    cv2.addWeighted(image, .15, np.zeros_like(image), .85, 0, dst=image)
    x = y = 0

    def label(text, row, color=(220, 240, 230)):
        cv2.putText(image, text, (x + 12, y + row), cv2.FONT_HERSHEY_SIMPLEX,
                    .48, color, 1, cv2.LINE_AA)

    label("CONTROL PREVIEW / NO HARDWARE", 23)
    label(f"C: calibrate at {control['reference_cm']:g} cm | R: reset", 46)
    state = control["status"].replace("_", " ").upper()
    label(f"{state}  ({control['calibration_samples']} samples)"
          if control["status"] in ("calibrating", "hold_still") else state, 69)
    distance = control["distance_cm"]
    label("Palm Z estimate: --" if distance is None else
          f"Palm Z estimate: {distance:.1f} cm | delta {control['delta_cm']:+.1f}", 94,
          (100, 230, 255))
    label("Finger flexion: straight 0 -> bent 1", 119)
    for i, name in enumerate(COLORS):
        value = control["flexion"].get(name)
        row = 147 + i * 27
        label(f"{name:6s}  {'--' if value is None else f'{value:.2f}'}", row, COLORS[name])
        left, right = x + min(170, panel_w // 2), x + panel_w - 16
        cv2.rectangle(image, (left, y + row - 11), (right, y + row), (60, 65, 60), -1)
        if value is not None:
            cv2.rectangle(image, (left, y + row - 11),
                          (left + int(value * (right - left)), y + row), COLORS[name], -1)
    label("Estimated only; thumb flexion excludes opposition", 298, (150, 170, 170))
    target[:] = cv2.resize(image, (rendered_w, rendered_h), interpolation=cv2.INTER_AREA)


def draw_metric_depth(image, depth, flexion):
    """Display metric camera coordinates separately from mirrored screen positions."""
    height, width = image.shape[:2]
    points = depth["points"]
    for point in points.values():
        if point["pixel_x"] is not None:
            cv2.circle(image, (width - 1 - point["pixel_x"], point["pixel_y"]), 3,
                       (80, 255, 80) if point["valid"] else (80, 80, 255), -1)
    panel_h = min(height, 245)
    panel = image[:panel_h, :]
    cv2.addWeighted(panel, .15, np.zeros_like(panel), .85, 0, dst=panel)

    def label(text, y, color=(230, 240, 230)):
        cv2.putText(image, text, (10, y), cv2.FONT_HERSHEY_SIMPLEX, .46, color, 1, cv2.LINE_AA)

    label("D455 + MEDIAPIPE | XYZ meters | NO MOTOR OUTPUT", 22)
    palm = points.get("Palm", {})
    z = palm.get("Z_m")
    tips = [points.get(name + "_Tip", {}) for name in COLORS]
    valid_tips = sum(bool(point.get("valid")) for point in tips)
    palm_label = "Palm Z: -- (no valid depth)" if z is None else f"Palm Z: {z * 100:.1f} cm"
    label(f"{palm_label} | Tips valid: {valid_tips}/5", 47, (100, 240, 255))
    label("Finger     X(m)     Y(m)     Z(m)    Curl(0-1)", 72)
    for row, name in enumerate(COLORS):
        point = points.get(name + "_Tip", {})
        values = ["   --" if point.get(axis) is None else f"{point[axis]:+7.3f}" for axis in ("X_m", "Y_m", "Z_m")]
        curl = flexion.get(name)
        label(f"{name:6s}  {'  '.join(values)}   {'--' if curl is None else f'{curl:.2f}'}",
              96 + row * 21, COLORS[name])
    label("XYZ: unmirrored camera; missing depth stays blank", 199, (170, 180, 180))
    if not points:
        hint = "Show your RIGHT hand; keep other hands out of view"
    else:
        holes = sum(point.get("reason") == "center_hole" for point in tips)
        sparse = sum(point.get("reason") == "sparse_depth" for point in tips)
        edges = sum(point.get("reason") == "depth_edge" for point in tips)
        hint = f"Missing tips: raw holes {holes}, sparse {sparse}, edges {edges}"
    label(hint, 224, (130, 210, 255))
