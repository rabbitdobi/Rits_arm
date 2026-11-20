"""Camera-independent motion measurements in mirrored screen coordinates."""

import math

FINGERTIPS = {"Thumb": 4, "Index": 8, "Middle": 12, "Ring": 16, "Pinky": 20}
# 3 landmarks per finger to calculate flexion angle (joint 1, joint 2, joint 3)
# The angle is measured at joint 2 formed by vector(2->1) and vector(2->3).
FINGER_JOINTS = {
    "Thumb":  (2, 3, 4),    # MCP, IP, TIP
    "Index":  (5, 6, 8),    # MCP, PIP, TIP
    "Middle": (9, 10, 12),  # MCP, PIP, TIP
    "Ring":   (13, 14, 16), # MCP, PIP, TIP
    "Pinky":  (17, 18, 20), # MCP, PIP, TIP
}
# Expected distance ratio (dist(wrist, tip) / palm_length) for open vs closed states
FINGER_DIST_RANGES = {
    "Thumb":  (1.20, 0.75),
    "Index":  (1.75, 0.95),
    "Middle": (1.90, 0.95),
    "Ring":   (1.75, 0.90),
    "Pinky":  (1.50, 0.85),
}
CSV_FIELDS = ["schema_version", "timestamp_ms", "tracked", "handedness_score",
              "finger", "x", "y", "vx", "vy", "speed", "angle"]


def _dist3d(p1, p2):
    return math.sqrt((p1.x - p2.x)**2 + (p1.y - p2.y)**2 + (getattr(p1, "z", 0.0) - getattr(p2, "z", 0.0))**2)


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
    Combines 3D joint angle with wrist-to-tip distance ratio so that fist flexion
    is maintained even when finger joints are occluded from the back of the hand.
    0 deg = straight/open, ~90-130 deg = bent/closed.
    """
    if landmarks is None or len(landmarks) < 21:
        return {}

    # Palm scale: distance from wrist(0) to middle MCP(9), and index MCP(5)
    p0, p5, p9 = landmarks[0], landmarks[5], landmarks[9]
    palm_len = _dist3d(p0, p9)
    if palm_len == 0:
        palm_len = 1.0

    angles = {}
    # 1. Calculate 4 fingers first (Index, Middle, Ring, Pinky)
    for name in ("Index", "Middle", "Ring", "Pinky"):
        j1, j2, j3 = FINGER_JOINTS[name]
        joint_angle = calculate_joint_angle(landmarks[j1], landmarks[j2], landmarks[j3])
        joint_bend = max(0.0, min(180.0, 180.0 - joint_angle))

        tip_idx = FINGERTIPS[name]
        d = _dist3d(p0, landmarks[tip_idx])
        r_open, r_closed = FINGER_DIST_RANGES[name]
        dist_ratio = max(0.0, min(1.0, (r_open - (d / palm_len)) / max(0.1, r_open - r_closed)))
        dist_bend = dist_ratio * 125.0
        angles[name] = round(max(joint_bend, dist_bend), 1)

    # 2. Calculate Thumb with joint angle, PIP proximity, and fist synergy
    j1, j2, j3 = FINGER_JOINTS["Thumb"]
    joint_angle = calculate_joint_angle(landmarks[j1], landmarks[j2], landmarks[j3])
    joint_bend = max(0.0, min(180.0, 180.0 - joint_angle))
    thumb_effective = max(0.0, joint_bend - 15.0)
    thumb_joint_bend = min(180.0, thumb_effective * 2.5)

    # In a fist, thumb tip (4) folds tightly beside index PIP (6)
    d_to_pip = _dist3d(landmarks[6], landmarks[4])
    pip_ratio = max(0.0, min(1.0, (0.80 - (d_to_pip / palm_len)) / (0.80 - 0.35)))
    thumb_dist_bend = pip_ratio * 125.0

    # Fist synergy assist: if the 4 fingers form a clenched fist (fist_avg > 70 deg),
    # the thumb naturally curls with the fist and maintains full closure even during wrist rotation / occlusion.
    fist_avg = (angles["Index"] + angles["Middle"] + angles["Ring"] + angles["Pinky"]) / 4.0
    synergy_bend = fist_avg * 0.95 if fist_avg > 70.0 else 0.0

    thumb_bend = max(thumb_joint_bend, thumb_dist_bend, synergy_bend)
    angles["Thumb"] = round(thumb_bend, 1)

    return angles


def calculate_wrist_roll(landmarks):
    """
    Calculate 360-degree wrist rotation (roll) angle in degrees from hand palm normal vector.
    Returns:
      deg_360: 0 to 360 deg (0 = palm facing camera, 90 = right, 180 = back, 270 = left)
      signed_deg: -180 to +180 deg (positive = right, negative = left, 0 = center/palm)
    """
    if landmarks is None or len(landmarks) < 21:
        return 0.0, 0.0
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
        return 0.0, 0.0
    # nx indicates left/right roll, nz indicates front/back
    signed_deg = math.degrees(math.atan2(nx, nz))
    deg_360 = signed_deg if signed_deg >= 0 else signed_deg + 360.0
    return round(deg_360, 1), round(signed_deg, 1)


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

        # Use 3D world landmarks (metric hand-local space) when available.
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
                max_noise = 3.0 if name == "Thumb" else 4.0
                if abs(filtered - old) < deadband and abs(raw - old) < max_noise:
                    val = old
                else:
                    val = filtered
            else:
                val = raw
            smoothed_angles[name] = round(val, 1)
        # Smooth wrist rotation in 0-360 deg space (avoids -180/+180 boundary jump)
        raw_wrist_360, raw_wrist_signed = calculate_wrist_roll(landmarks)
        if self.previous_angles is not None and "Wrist" in self.previous_angles:
            old_w = self.previous_angles["Wrist"]
            # Shortest-path difference in 0-360 circle (wrap-around safe)
            diff = raw_wrist_360 - old_w
            if diff > 180:
                diff -= 360.0
            elif diff < -180:
                diff += 360.0
            filtered_w = old_w + angle_alpha * diff
            # Keep in 0-360 range
            filtered_w = filtered_w % 360.0
            if abs(angle_alpha * diff) < 1.0 and abs(diff) < 2.5:
                smoothed_360 = old_w
            else:
                smoothed_360 = filtered_w
        else:
            smoothed_360 = raw_wrist_360
        smoothed_angles["Wrist"] = round(smoothed_360, 1)

        # Signed version (-180 to +180) for display only
        signed = smoothed_360 if smoothed_360 <= 180 else smoothed_360 - 360.0
        smoothed_angles["Wrist_signed"] = round(signed, 1)

        # Left / Right direction detection
        if signed > 10.0:
            wrist_dir = "RIGHT"
        elif signed < -10.0:
            wrist_dir = "LEFT"
        else:
            wrist_dir = "CENTER"

        self.previous_angles = smoothed_angles

        # 6 values for robot control: 5 fingers + wrist rotation
        finger_angles = [smoothed_angles.get(f, 0.0) for f in ("Thumb", "Index", "Middle", "Ring", "Pinky", "Wrist")]
        frame["angles"] = smoothed_angles
        frame["finger_angles"] = finger_angles
        frame["wrist_angle"] = smoothed_angles["Wrist"]
        frame["wrist_signed_angle"] = smoothed_angles["Wrist_signed"]
        frame["wrist_direction"] = wrist_dir

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
