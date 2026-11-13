"""Camera-independent motion measurements in mirrored screen coordinates."""

import math

FINGERTIPS = {"Thumb": 4, "Index": 8, "Middle": 12, "Ring": 16, "Pinky": 20}
# 3 landmarks per finger to calculate flexion angle (joint 1, joint 2, joint 3)
# The angle is measured at joint 2 formed by vector(2->1) and vector(2->3).
FINGER_JOINTS = {
    "Thumb":  (2, 3, 4),    # MCP, IP, TIP (pure thumb joints, immune to wrist rotation)
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


def calculate_wrist_roll(landmarks):
    """
    Calculate wrist rotation (roll) angle in degrees from hand palm normal vector.
    0 deg = palm facing camera, 90 deg = sideways (chop), 180 deg = back of hand facing camera.
    """
    if landmarks is None or len(landmarks) < 21:
        return 0.0
    # Landmarks: Wrist (0), Index MCP (5), Middle MCP (9), Pinky MCP (17)
    p0, p5, p9, p17 = landmarks[0], landmarks[5], landmarks[9], landmarks[17]
    u = (p5.x - p17.x, p5.y - p17.y, getattr(p5, "z", 0.0) - getattr(p17, "z", 0.0))
    v = (p9.x - p0.x, p9.y - p0.y, getattr(p9, "z", 0.0) - getattr(p0, "z", 0.0))
    # Normal vector = u x v
    nx = u[1] * v[2] - u[2] * v[1]
    ny = u[2] * v[0] - u[0] * v[2]
    nz = u[0] * v[1] - u[1] * v[0]
    norm = math.sqrt(nx**2 + ny**2 + nz**2)
    if norm == 0:
        return 90.0
    cos_theta = max(-1.0, min(1.0, nz / norm))
    angle = math.degrees(math.acos(cos_theta))
    return round(angle, 1)


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
        self.previous_angles = None
        self.last_timestamp = None

    def update(self, landmarks, timestamp_ms, score=None, world_landmarks=None):
        if self.last_timestamp is not None and timestamp_ms <= self.last_timestamp:
            raise ValueError("Frame timestamps must strictly increase")
        dt_ms = None if self.last_timestamp is None else timestamp_ms - self.last_timestamp
        self.last_timestamp = timestamp_ms

        frame = {"schema_version": 1, "timestamp_ms": timestamp_ms,
                 "tracked": landmarks is not None,
                 "handedness_score": score if landmarks is not None else None,
                 "fingers": {},
                 "angles": {},
                 "finger_angles": []}
        if landmarks is None:
            self.previous = None
            self.previous_angles = None
            return frame
        if dt_ms is not None and dt_ms > self.max_gap_ms:
            self.previous = None
            self.previous_angles = None
        alpha = (1 - math.exp(-dt_ms / self.smoothing_ms)
                 if dt_ms is not None and self.smoothing_ms > 0 else 1)

        # Use 3D world landmarks (metric hand-local space) when available
        # so lateral/vertical hand motion does not distort finger bend angles!
        angle_landmarks = (world_landmarks if world_landmarks is not None and len(world_landmarks) >= 21
                           else landmarks)
        raw_angles = calculate_finger_angles(angle_landmarks)
        # 150ms time constant suppresses camera landmark fluctuations
        angle_alpha = (1 - math.exp(-dt_ms / 150.0)
                       if dt_ms is not None and dt_ms > 0 else alpha)
        smoothed_angles = {}
        for name in FINGER_JOINTS:
            raw = raw_angles.get(name, 0.0)
            if self.previous_angles is not None and name in self.previous_angles:
                old = self.previous_angles[name]
                filtered = old + angle_alpha * (raw - old)
                # Deadband: ignore small jitter when hand is steady (thumb gets slightly wider deadband)
                deadband = 1.5 if name == "Thumb" else 1.0
                max_noise = 3.0 if name == "Thumb" else 2.5
                if abs(filtered - old) < deadband and abs(raw - old) < max_noise:
                    val = old
                else:
                    val = filtered
            else:
                val = raw
            smoothed_angles[name] = round(val, 1)
        # Smooth wrist rotation (roll) angle
        raw_wrist = calculate_wrist_roll(landmarks)
        if self.previous_angles is not None and "Wrist" in self.previous_angles:
            old_w = self.previous_angles["Wrist"]
            filtered_w = old_w + angle_alpha * (raw_wrist - old_w)
            if abs(filtered_w - old_w) < 1.0 and abs(raw_wrist - old_w) < 2.5:
                smoothed_wrist = old_w
            else:
                smoothed_wrist = filtered_w
        else:
            smoothed_wrist = raw_wrist
        smoothed_angles["Wrist"] = round(smoothed_wrist, 1)

        self.previous_angles = smoothed_angles

        # 6 values for robot control: 5 fingers + wrist rotation
        finger_angles = [smoothed_angles.get(f, 0.0) for f in ("Thumb", "Index", "Middle", "Ring", "Pinky", "Wrist")]
        frame["angles"] = smoothed_angles
        frame["finger_angles"] = finger_angles
        frame["wrist_angle"] = smoothed_angles["Wrist"]

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
                                          angle=smoothed_angles.get(name, 0.0))
        self.previous = frame["fingers"]
        return frame


def write_csv_frame(writer, frame):
    metadata = {key: frame[key] for key in CSV_FIELDS[:4]}
    if not frame["tracked"]:
        writer.writerow(metadata)
    else:
        for name, finger in frame["fingers"].items():
            writer.writerow(dict(metadata, finger=name, **finger))
