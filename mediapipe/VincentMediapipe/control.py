"""Camera-only measurements for a visual prototype; never motor commands."""

from collections import deque
import math
from statistics import median

CHAINS = {"Thumb": (1, 2, 3, 4), "Index": (5, 6, 7, 8),
          "Middle": (9, 10, 11, 12), "Ring": (13, 14, 15, 16),
          "Pinky": (17, 18, 19, 20)}


def vector(a, b):
    return tuple(y - x for x, y in zip(a, b))


def norm(v):
    return math.sqrt(sum(x * x for x in v))


def flexion(points):
    result = {}
    for name, chain in CHAINS.items():
        bends = []
        for a, b, c in zip(chain, chain[1:], chain[2:]):
            u, v = vector(points[b], points[a]), vector(points[b], points[c])
            denominator = norm(u) * norm(v)
            if denominator < 1e-12:
                break
            cosine = max(-1., min(1., sum(x * y for x, y in zip(u, v)) / denominator))
            bends.append(180 - math.degrees(math.acos(cosine)))
        result[name] = min(1., max(0., sum(bends) / 180)) if len(bends) == 2 else None
    return result


class ControlTracker:
    def __init__(self, reference_cm=40, smoothing_ms=100):
        if not math.isfinite(reference_cm) or reference_cm <= 0:
            raise ValueError("Reference distance must be positive and finite")
        self.reference_cm = reference_cm
        self.smoothing_ms = smoothing_ms
        self.last_timestamp = None
        self.reset()

    def reset(self):
        self.calibration = None
        self.collecting = False
        self.samples = deque(maxlen=120)
        self.previous_distance = None

    def request_calibration(self):
        self.reset()
        self.collecting = True

    def update(self, landmarks, world_landmarks, timestamp_ms, image_size):
        if self.last_timestamp is not None and timestamp_ms <= self.last_timestamp:
            raise ValueError("Frame timestamps must strictly increase")
        dt = None if self.last_timestamp is None else timestamp_ms - self.last_timestamp
        self.last_timestamp = timestamp_ms
        if dt is not None and dt > 250:
            self.previous_distance = None
            self.samples.clear()
        result = {"schema_version": 1, "method": "palm_scale_estimate",
                  "status": "uncalibrated", "distance_cm": None, "delta_cm": None,
                  "flexion": {}, "world_landmarks_m": None, "frontality": None,
                  "calibration_samples": 0, "calibration": self.calibration,
                  "reference_cm": self.reference_cm}

        def invalid(reason):
            result["status"] = reason
            self.previous_distance = None
            self.samples.clear()
            return result

        if landmarks is None or world_landmarks is None:
            return invalid("hand_lost")
        try:
            if len(landmarks) != 21 or len(world_landmarks) != 21:
                return invalid("invalid_landmarks")
            points = [(p.x, p.y, p.z) for p in world_landmarks]
            if (not all(math.isfinite(v) for p in points for v in p) or
                    not all(math.isfinite(v) and 0 <= v <= 1
                            for p in landmarks for v in (p.x, p.y))):
                return invalid("invalid_landmarks")
        except (AttributeError, TypeError):
            return invalid("invalid_landmarks")
        result["flexion"] = flexion(points)
        result["world_landmarks_m"] = [dict(zip(("x", "y", "z"), p)) for p in points]
        u, v = vector(points[0], points[5]), vector(points[0], points[17])
        normal = (u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2],
                  u[0] * v[1] - u[1] * v[0])
        length = norm(normal)
        if length < 1e-9:
            return invalid("invalid_palm")
        result["frontality"] = abs(normal[2]) / length
        if result["frontality"] < .8:
            return invalid("face_camera")

        width, height = image_size
        pixels = [(p.x * width, p.y * height) for p in landmarks]
        spans = (norm(vector(pixels[5], pixels[17])), norm(vector(pixels[0], pixels[9])))
        if min(spans) < 8:
            return invalid("palm_too_small")
        if self.collecting:
            self.samples.append((timestamp_ms, *spans))
            result["status"] = "calibrating"
            result["calibration_samples"] = len(self.samples)
            if len(self.samples) >= 20 and timestamp_ms - self.samples[0][0] >= 800:
                bases = tuple(median(s[i] for s in self.samples) for i in (1, 2))
                stable = all(abs(s[i + 1] / bases[i] - 1) <= .1
                             for s in self.samples for i in (0, 1))
                if not stable:
                    result["status"] = "hold_still"
                    return result
                self.calibration = {"reference_cm": self.reference_cm,
                                    "width_px": bases[0], "length_px": bases[1],
                                    "image_size": list(image_size),
                                    "timestamp_ms": timestamp_ms}
                self.collecting = False
            else:
                return result
        result["calibration"] = self.calibration
        if self.calibration is None:
            return result
        if list(image_size) != self.calibration["image_size"]:
            return invalid("resolution_changed_recalibrate")
        ratios = (self.calibration["width_px"] / spans[0],
                  self.calibration["length_px"] / spans[1])
        if max(ratios) / min(ratios) > 1.2:
            return invalid("palm_shape_changed")
        distance = self.reference_cm * math.sqrt(ratios[0] * ratios[1])
        if not math.isfinite(distance):
            return invalid("invalid_distance")
        if self.previous_distance is not None and dt is not None and self.smoothing_ms > 0:
            alpha = 1 - math.exp(-dt / self.smoothing_ms)
            distance = self.previous_distance + alpha * (distance - self.previous_distance)
        self.previous_distance = distance
        result.update(status="estimated", distance_cm=distance,
                      delta_cm=distance - self.reference_cm)
        return result
