"""Aligned D455 acquisition and conservative metric landmark measurements."""

import math
import os
import json

import numpy as np

JOINTS = ["Wrist", "Thumb_CMC", "Thumb_MCP", "Thumb_IP", "Thumb_Tip",
          "Index_MCP", "Index_PIP", "Index_DIP", "Index_Tip",
          "Middle_MCP", "Middle_PIP", "Middle_DIP", "Middle_Tip",
          "Ring_MCP", "Ring_PIP", "Ring_DIP", "Ring_Tip",
          "Pinky_MCP", "Pinky_PIP", "Pinky_DIP", "Pinky_Tip"]
DEPTH_FIELDS = ["timestamp_ms", "tracked", "handedness_score", "joint", "valid",
                "reason", "pixel_x", "pixel_y", "X_m", "Y_m", "Z_m",
                "valid_fraction", "spread_m"]


def sample_point(raw, scale, x, y, deproject):
    point = dict(valid=False, reason="invalid_pixel", pixel_x=None, pixel_y=None,
                 X_m=None, Y_m=None, Z_m=None, valid_fraction=0., spread_m=None)
    if not math.isfinite(scale) or scale <= 0:
        raise ValueError("Depth scale must be positive and finite")
    if not (math.isfinite(x) and math.isfinite(y) and 0 <= x < 1 and 0 <= y < 1):
        return point
    height, width = raw.shape
    u, v = x * width, y * height
    px, py = int(u), int(v)
    point.update(pixel_x=px, pixel_y=py)
    center = float(raw[py, px])
    patch = raw[max(0, py - 1):min(height, py + 2), max(0, px - 1):min(width, px + 2)]
    valid = np.isfinite(patch) & (patch > 0)
    point["valid_fraction"] = float(valid.mean())
    values = patch[valid].astype(float) * scale
    spread = float(values.max() - values.min()) if values.size else None
    point["spread_m"] = spread if spread is not None and math.isfinite(spread) else None
    # Measure the neighborhood for diagnosis, but never fill an invalid center.
    if not math.isfinite(center) or center <= 0:
        point["reason"] = "center_hole"
        return point
    if point["valid_fraction"] < .6:
        point["reason"] = "sparse_depth"
        return point
    z = float(np.median(values))
    if not math.isfinite(z) or not math.isfinite(spread) or spread > max(.03, z * .05):
        point["reason"] = "depth_edge"
        return point
    xyz = deproject([u, v], z)
    if len(xyz) != 3 or not all(math.isfinite(value) for value in xyz):
        point["reason"] = "invalid_xyz"
        return point
    point.update(valid=True, reason="ok", X_m=float(xyz[0]), Y_m=float(xyz[1]), Z_m=float(xyz[2]))
    return point


def metric_hand(landmarks, raw, scale, deproject):
    result = {"schema_version": 1, "units": "m", "coordinate_frame": "d455_color_optical",
              "points": {}}
    if landmarks is None:
        return result
    for index, name in enumerate(JOINTS):
        p = landmarks[index]
        result["points"][name] = sample_point(raw, scale, p.x, p.y, deproject)
    palm = [landmarks[i] for i in (0, 5, 9, 13, 17)]
    result["points"]["Palm"] = sample_point(raw, scale, sum(p.x for p in palm) / 5,
                                            sum(p.y for p in palm) / 5, deproject)
    return result


def write_depth_csv(writer, depth, timestamp_ms, tracked, score):
    base = dict(timestamp_ms=timestamp_ms, tracked=tracked, handedness_score=score)
    if not depth["points"]:
        writer.writerow(dict(base, valid=False, reason="hand_lost"))
    for name, point in depth["points"].items():
        writer.writerow(dict(base, joint=name, **point))


def restore_user_ownership(paths):
    if os.geteuid() == 0 and os.environ.get("SUDO_UID"):
        uid, gid = int(os.environ["SUDO_UID"]), int(os.environ["SUDO_GID"])
        for path in paths:
            if path.exists():
                os.chown(path, uid, gid)


def ensure_output_directory(directory, created_paths):
    """Remember only directories this process actually creates, for sudo cleanup."""
    missing = []
    current = directory
    while not current.exists():
        missing.append(current)
        current = current.parent
    for path in reversed(missing):
        try:
            path.mkdir()
        except FileExistsError:
            if not path.is_dir():
                raise
        else:
            created_paths.append(path)


def save_depth_sample(directory, index, raw, color, scale, landmarks, frame, created_paths, native_raw=None):
    """Optional same-frame evidence, saved before any preview mirroring/overlays."""
    arrays = directory / f"{index:06d}.npz"
    metadata_path = directory / f"{index:06d}.json"
    with arrays.open("xb") as file:
        created_paths.append(arrays)
        payload = dict(depth_z16=raw, color_bgr=color, meters_per_unit=scale)
        if native_raw is not None:
            payload["native_depth_z16"] = native_raw
        np.savez_compressed(file, **payload)
    normalized = None if landmarks is None else [
        {axis: float(getattr(p, axis)) if math.isfinite(getattr(p, axis)) else None
         for axis in ("x", "y", "z")} for p in landmarks]
    metadata = {"sample_version": 1, "timestamp_ms": frame.get("timestamp_ms"),
                "handedness_score": frame.get("handedness_score"), "landmarks": normalized,
                "depth": frame.get("depth"), "color_mirrored": False}
    if "human_arm" in frame:
        metadata["human_arm"] = frame["human_arm"]
    with metadata_path.open("x", encoding="utf-8") as file:
        created_paths.append(metadata_path)
        json.dump(metadata, file, allow_nan=False)


class RealSenseSource:
    def __init__(self, frame_timeout_ms=10000):
        import pyrealsense2 as rs

        self.rs = rs
        self.frame_timeout_ms = frame_timeout_ms
        self.context = rs.context()
        devices = [d for d in self.context.query_devices() if "D455" in d.get_info(rs.camera_info.name)]
        if len(devices) != 1:
            message = (" On macOS use the D455 Terminal launcher for USB access."
                       if os.uname().sysname == "Darwin" else " On Linux check the USB cable and RealSense udev rules.")
            raise RuntimeError("Connect exactly one accessible D455." + message)
        device = devices[0]
        self.pipeline = rs.pipeline(self.context)
        config = rs.config()
        config.enable_device(device.get_info(rs.camera_info.serial_number))
        config.enable_stream(rs.stream.color, 640, 480, rs.format.bgr8, 30)
        config.enable_stream(rs.stream.depth, 640, 480, rs.format.z16, 30)
        self.started = False
        try:
            profile = self.pipeline.start(config)
            self.started = True
            self.scale = profile.get_device().first_depth_sensor().get_depth_scale()
            self.align = rs.align(rs.stream.color)
            self.colorizer = rs.colorizer()
            color_intrinsics = profile.get_stream(rs.stream.color).as_video_stream_profile().get_intrinsics()
            depth_profile = profile.get_stream(rs.stream.depth).as_video_stream_profile()
            native_intrinsics = depth_profile.get_intrinsics()
            extrinsics = depth_profile.get_extrinsics_to(profile.get_stream(rs.stream.color))
            self.metadata = {"schema_version": 1, "camera": device.get_info(rs.camera_info.name),
                             "firmware": device.get_info(rs.camera_info.firmware_version),
                             "usb_type": device.get_info(rs.camera_info.usb_type_descriptor),
                             "meters_per_unit": self.scale, "aligned_to": "color", "units": "m",
                             "coordinate_frame": "d455_color_optical", "axes": "+X right, +Y down, +Z forward",
                             "preview_mirrored": True, "metric_coordinates_mirrored": False,
                             "sampling": "3x3 median, center valid, >=60% coverage, spread <= max(0.03m, 5%)",
                             "intrinsics": {k: getattr(color_intrinsics, k) for k in
                                            ("width", "height", "fx", "fy", "ppx", "ppy", "coeffs")},
                             "distortion_model": str(color_intrinsics.model)}
            self.metadata["native_depth_intrinsics"] = {
                k: getattr(native_intrinsics, k) for k in
                ("width", "height", "fx", "fy", "ppx", "ppy", "coeffs")}
            self.metadata["native_distortion_model"] = str(native_intrinsics.model)
            self.metadata["depth_to_color_extrinsics"] = {
                "rotation": extrinsics.rotation, "translation": extrinsics.translation}
            for _ in range(30):
                self.pipeline.wait_for_frames(10000)
            self.first_timestamp = None
            self.timestamp_ms = None
            self.raw = None
        except BaseException:
            self.release()
            raise

    def isOpened(self):
        return self.started

    def read(self):
        frames = self.pipeline.wait_for_frames(self.frame_timeout_ms)
        native_depth = frames.get_depth_frame()
        if not native_depth:
            raise RuntimeError("D455 frameset missing native depth")
        self.native_raw = np.asanyarray(native_depth.get_data()).copy()
        aligned = self.align.process(frames)
        self.depth_frame = aligned.get_depth_frame()
        color = aligned.get_color_frame()
        if not self.depth_frame or not color:
            raise RuntimeError("D455 aligned frameset missing depth/color")
        timestamp = color.get_timestamp()
        if self.first_timestamp is None:
            self.first_timestamp = timestamp
        self.timestamp_ms = timestamp - self.first_timestamp
        self.capture_metadata = {"color_timestamp_ms": timestamp,
                                 "depth_timestamp_ms": self.depth_frame.get_timestamp(),
                                 "color_frame_number": color.get_frame_number(),
                                 "depth_frame_number": self.depth_frame.get_frame_number()}
        self.capture_metadata["native_valid_fraction"] = float((self.native_raw > 0).mean())
        self.raw = np.asanyarray(self.depth_frame.get_data()).copy()
        self.capture_metadata["aligned_valid_fraction"] = float((self.raw > 0).mean())
        self.intrinsics = self.depth_frame.profile.as_video_stream_profile().get_intrinsics()
        return True, np.asanyarray(color.get_data()).copy()

    def measure(self, landmarks):
        depth = metric_hand(landmarks, self.raw, self.scale,
                            lambda pixel, z: self.rs.rs2_deproject_pixel_to_point(self.intrinsics, pixel, z))
        depth.update(self.capture_metadata)
        return depth

    def depth_view(self):
        import cv2

        colorized = np.asanyarray(self.colorizer.colorize(self.depth_frame).get_data())
        return cv2.flip(cv2.cvtColor(colorized, cv2.COLOR_RGB2BGR), 1)

    def release(self):
        if self.started:
            self.started = False
            self.pipeline.stop()
