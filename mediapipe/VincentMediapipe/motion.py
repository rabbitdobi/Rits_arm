"""Camera-independent motion measurements in mirrored screen coordinates."""

import math

FINGERTIPS = {"Thumb": 4, "Index": 8, "Middle": 12, "Ring": 16, "Pinky": 20}
# 3 landmarks per finger to calculate flexion angle (joint 1, joint 2, joint 3)
# The angle is measured at joint 2 formed by vector(2->1) and vector(2->3).
FINGER_JOINTS = {
    "Thumb":  (1, 2, 4),    # CMC, MCP, TIP
    "Index":  (5, 6, 8),    # MCP, PIP, TIP
    "Middle": (9, 10, 12),  # MCP, PIP, TIP
    "Ring":   (13, 14, 16), # MCP, PIP, TIP
    "Pinky":  (17, 18, 20), # MCP, PIP, TIP
}
CSV_FIELDS = ["schema_version", "timestamp_ms", "tracked", "handedness_score",
              "finger", "x", "y", "vx", "vy", "speed", "angle"]


def calculate_joint_angle(p1, p2, p3):
    """Calculate 3D angle at joint p2 formed by (p1 - p2) and (p3 - p2) in degrees."""
    v1 = (p1.x - p2.x, p1.y - p2.y, getattr(p1, "z", 0.0) - getattr(p2, "z", 0.0))
    v2 = (p3.x - p2.x, p3.y - p2.y, getattr(p3, "z", 0.0) - getattr(p2, "z", 0.0))
    dot = v1[0] * v2[0] + v1[1] * v2[1] + v1[2] * v2[2]
    norm1 = math.sqrt(v1[0]**2 + v1[1]**2 + v1[2]**2)
    norm2 = math.sqrt(v2[0]**2 + v2[1]**2 + v2[2]**2)
    if norm1 * norm2 == 0:
        return 180.0
    cosine = max(-1.0, min(1.0, dot / (norm1 * norm2)))
    return math.degrees(math.acos(cosine))


def calculate_finger_angles(landmarks):
    """
    Calculate bend/flex angles (in degrees) for 5 fingers.
    0 deg = straight/open, ~90-130 deg = bent/closed.
    """
    if landmarks is None or len(landmarks) < 21:
        return {}
    angles = {}
    for name, (j1, j2, j3) in FINGER_JOINTS.items():
        angle = calculate_joint_angle(landmarks[j1], landmarks[j2], landmarks[j3])
        # 180 deg is fully straight. Flex angle = 180 - angle.
        bend = max(0.0, min(180.0, 180.0 - angle))
        angles[name] = round(bend, 1)
    return angles


def select_right_hand(result, min_score=0.6):
    """Select the most confident subject-right hand in an unmirrored input."""
    candidates = [(category.score, index)
                  for index, categories in enumerate(result.handedness)
                  if index < len(result.hand_landmarks)
                  for category in categories
                  if category.category_name == "Right" and category.score >= min_score]
    return max(candidates)[1] if candidates else None


class MotionTracker:
    def __init__(self, smoothing_ms=60, max_gap_ms=250):
        self.smoothing_ms = smoothing_ms
        self.max_gap_ms = max_gap_ms
        self.previous = None
        self.last_timestamp = None

    def update(self, landmarks, timestamp_ms, score=None):
        if self.last_timestamp is not None and timestamp_ms <= self.last_timestamp:
            raise ValueError("Frame timestamps must strictly increase")
        dt_ms = None if self.last_timestamp is None else timestamp_ms - self.last_timestamp
        self.last_timestamp = timestamp_ms
        angles = calculate_finger_angles(landmarks)
        finger_angles = [angles.get(f, 0.0) for f in ("Thumb", "Index", "Middle", "Ring", "Pinky")]
        frame = {"schema_version": 1, "timestamp_ms": timestamp_ms,
                 "tracked": landmarks is not None,
                 "handedness_score": score if landmarks is not None else None,
                 "fingers": {},
                 "angles": angles,
                 "finger_angles": finger_angles}
        if landmarks is None:
            self.previous = None
            return frame
        if dt_ms is not None and dt_ms > self.max_gap_ms:
            self.previous = None
        alpha = (1 - math.exp(-dt_ms / self.smoothing_ms)
                 if dt_ms is not None and self.smoothing_ms > 0 else 1)
        for name, index in FINGERTIPS.items():
            x, y = 1.0 - landmarks[index].x, landmarks[index].y
            vx = vy = speed = None
            if self.previous is not None:
                old = self.previous[name]
                x = old["x"] + alpha * (x - old["x"])
                y = old["y"] + alpha * (y - old["y"])
                vx = (x - old["x"]) / (dt_ms / 1000)
                vy = (y - old["y"]) / (dt_ms / 1000)
                speed = math.hypot(vx, vy)
            frame["fingers"][name] = dict(x=x, y=y, vx=vx, vy=vy, speed=speed,
                                          angle=angles.get(name, 0.0))
        self.previous = frame["fingers"]
        return frame


def write_csv_frame(writer, frame):
    metadata = {key: frame[key] for key in CSV_FIELDS[:4]}
    if not frame["tracked"]:
        writer.writerow(metadata)
    else:
        for name, finger in frame["fingers"].items():
            writer.writerow(dict(metadata, finger=name, **finger))
