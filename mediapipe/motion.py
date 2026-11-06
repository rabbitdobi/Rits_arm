"""Camera-independent motion measurements in mirrored screen coordinates."""

import math

FINGERTIPS = {"Thumb": 4, "Index": 8, "Middle": 12, "Ring": 16, "Pinky": 20}
CSV_FIELDS = ["schema_version", "timestamp_ms", "tracked", "handedness_score",
              "finger", "x", "y", "vx", "vy", "speed"]


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
        frame = {"schema_version": 1, "timestamp_ms": timestamp_ms,
                 "tracked": landmarks is not None,
                 "handedness_score": score if landmarks is not None else None,
                 "fingers": {}}
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
            frame["fingers"][name] = dict(x=x, y=y, vx=vx, vy=vy, speed=speed)
        self.previous = frame["fingers"]
        return frame


def write_csv_frame(writer, frame):
    metadata = {key: frame[key] for key in CSV_FIELDS[:4]}
    if not frame["tracked"]:
        writer.writerow(metadata)
    else:
        for name, finger in frame["fingers"].items():
            writer.writerow(dict(metadata, finger=name, **finger))
