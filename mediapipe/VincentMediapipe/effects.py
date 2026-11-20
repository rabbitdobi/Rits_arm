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
    panel_height, panel_width = min(height, 195), min(width, 390)
    panel = image[:panel_height, :panel_width]
    cv2.addWeighted(panel, 0.25, np.zeros_like(panel), 0.75, 0, dst=panel)
    status = "RIGHT HAND" if frame["tracked"] else "RIGHT HAND LOST - show your right hand"
    cv2.putText(image, f"{status} | {fps:.0f} FPS", (12, 23),
                cv2.FONT_HERSHEY_SIMPLEX, 0.53, (220, 255, 230), 1, cv2.LINE_AA)

    bar_x = 80
    bar_w = 150
    bar_h = 10
    max_finger_angle = 130.0

    # 5本指のゲージバー
    for row, (name, finger) in enumerate(frame["fingers"].items()):
        y_text = 47 + row * 24
        y_bar = y_text - 10
        angle = finger.get("angle", 0.0)
        color = COLORS[name]

        # 指名
        cv2.putText(image, f"{name:6s}", (12, y_text), cv2.FONT_HERSHEY_SIMPLEX,
                    0.46, color, 1, cv2.LINE_AA)

        # ゲージ背景
        cv2.rectangle(image, (bar_x, y_bar), (bar_x + bar_w, y_bar + bar_h), (50, 50, 50), -1)

        # ゲージの伸び（曲げ角度）
        fill = int(max(0.0, min(1.0, angle / max_finger_angle)) * bar_w)
        if fill > 0:
            cv2.rectangle(image, (bar_x, y_bar), (bar_x + fill, y_bar + bar_h), color, -1)
        cv2.rectangle(image, (bar_x, y_bar), (bar_x + bar_w, y_bar + bar_h), (90, 90, 90), 1)

        # 角度数値
        cv2.putText(image, f"{angle:3.0f}deg", (bar_x + bar_w + 10, y_text),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.44, (230, 230, 230), 1, cv2.LINE_AA)

    # 手首（Wrist）の中央振り分けゲージバー
    y_wrist = 47 + 5 * 24
    y_bar_w = y_wrist - 10
    wrist = frame.get("wrist_angle", 0.0)
    wrist_dir = frame.get("wrist_direction", "CENTER")
    signed = frame.get("wrist_signed_angle", 0.0)
    wrist_color = (220, 220, 255)

    cv2.putText(image, "Wrist ", (12, y_wrist), cv2.FONT_HERSHEY_SIMPLEX,
                0.46, wrist_color, 1, cv2.LINE_AA)

    # 手首ゲージ背景
    cv2.rectangle(image, (bar_x, y_bar_w), (bar_x + bar_w, y_bar_w + bar_h), (50, 50, 50), -1)
    center_x = bar_x + bar_w // 2
    cv2.line(image, (center_x, y_bar_w - 2), (center_x, y_bar_w + bar_h + 2), (180, 180, 180), 1)

    # 左右の傾き（-90度〜+90度で左右フル）
    w_ratio = max(-1.0, min(1.0, signed / 90.0))
    offset = int(w_ratio * (bar_w // 2))
    if offset > 0:
        cv2.rectangle(image, (center_x, y_bar_w), (center_x + offset, y_bar_w + bar_h), (100, 200, 255), -1)
    elif offset < 0:
        cv2.rectangle(image, (center_x + offset, y_bar_w), (center_x, y_bar_w + bar_h), (255, 180, 100), -1)
    cv2.rectangle(image, (bar_x, y_bar_w), (bar_x + bar_w, y_bar_w + bar_h), (90, 90, 90), 1)

    # 手首数値と方向
    dir_str = "R" if wrist_dir == "RIGHT" else ("L" if wrist_dir == "LEFT" else "C")
    cv2.putText(image, f"{wrist:3.0f}deg [{dir_str}]", (bar_x + bar_w + 10, y_wrist),
                cv2.FONT_HERSHEY_SIMPLEX, 0.44, wrist_color, 1, cv2.LINE_AA)
