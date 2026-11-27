"""Simulation-only hand targets. This module has no hardware transport."""
from collections import deque
import math
import numpy as np
from arm_simulation import ArmModel


def coordinates(points):
    try:
        values = np.array([[p.x, p.y, p.z] for p in points], dtype=float)
        return values if values.shape == (21, 3) and np.isfinite(values).all() else None
    except (TypeError, AttributeError, ValueError):
        return None


def palm_frame(points):
    p = coordinates(points)
    if p is None:
        return None
    x = p[5] - p[17]
    if np.linalg.norm(x) < 1e-6:
        return None
    x /= np.linalg.norm(x)
    y = p[[5, 9, 13, 17]].mean(axis=0) - p[0]
    y -= np.dot(y, x) * x
    if np.linalg.norm(y) < 1e-6:
        return None
    y /= np.linalg.norm(y)
    return np.column_stack((x, y, np.cross(x, y)))


class UnifiedController:
    def __init__(self, config=None, smoothing_ms=80):
        self.model = ArmModel(config)
        self.smoothing_ms = float(smoothing_ms)
        if not math.isfinite(self.smoothing_ms) or self.smoothing_ms < 0:
            raise ValueError('Invalid smoothing duration')
        self.anchor = self.model.solve(self.model.config['origin_target_m'])
        if not self.anchor['valid']:
            raise ValueError('Model origin target is unreachable')
        self.timestamp = None
        self.reset()

    def reset(self):
        self.history = deque(maxlen=120)
        self.calibration = {}
        self.current_frame = self.current_palm = None
        self.origin = self.neutral = self.smoothed = None
        self.last_depth_time = None
        self.last_joints = self.anchor['joints_rad'][:]
        self.message = 'O: open hand, F: fist, W: neutral wrist, Space: arm origin'

    def calibrate_fingers(self, pose):
        if pose not in ('open', 'fist'):
            raise ValueError('Expected open or fist')
        if len(self.history) < 10 or self.history[-1][0] - self.history[0][0] < 250:
            self.message = 'Hold the hand steady for at least 10 frames'
            return False
        samples = np.array([v for _, v in self.history])
        if np.max(np.ptp(samples, axis=0)) > .15:
            self.message = 'Hand moved: hold the calibration pose steady'
            return False
        candidate = np.median(samples, axis=0)
        other = 'fist' if pose == 'open' else 'open'
        if other in self.calibration:
            opened = candidate if pose == 'open' else self.calibration[other]
            closed = candidate if pose == 'fist' else self.calibration[other]
            if np.any(opened - closed < .1):
                self.message = 'Calibration rejected: open and fist need distinct poses'
                return False
        self.calibration[pose] = candidate
        self.smoothed = None
        self.message = pose.capitalize() + ' calibration saved'
        return True

    def calibrate_wrist(self):
        if self.current_frame is None:
            self.message = 'No valid palm orientation'
            return False
        self.neutral = self.current_frame.copy()
        self.message = 'Palm twist neutral saved (orientation proxy)'
        return True

    def capture_origin(self):
        if self.current_palm is None:
            self.message = 'No valid measured palm depth'
            return False
        self.origin = self.current_palm.copy()
        self.last_joints = self.anchor['joints_rad'][:]
        self.message = 'Arm origin saved; simulation only'
        return True

    def update(self, points, depth, timestamp_ms):
        t = float(timestamp_ms)
        if not math.isfinite(t) or self.timestamp is not None and t <= self.timestamp:
            raise ValueError('Timestamps must increase and be finite')
        dt = 0 if self.timestamp is None else (t - self.timestamp) / 1000
        if dt > .25:
            self.history.clear()
            self.smoothed = None
        self.timestamp = t
        p = coordinates(points)
        self.current_frame = palm_frame(points)
        valid = p is not None and self.current_frame is not None and np.linalg.norm(p[9] - p[0]) > 1e-6
        fingers = dict(valid=False, reason='hand_unavailable', features=None, targets_0_180=None, serial_preview=None)
        wrist = dict(valid=False, reason='hand_unavailable', twist_rad=None, servo_preview_deg=None,
                     clamped=False, actuator=self.model.config['wrist_actuator'])
        arm = dict(valid=False, reason='depth_unavailable', camera_delta_m=None, target_m=None,
                   ik_solution_rad=None, joint_targets_rad=None, preview_m=None,
                   last_preview_joints_rad=self.last_joints[:])
        if valid:
            features = np.array([np.linalg.norm(p[4] - p[17])] + [np.linalg.norm(p[i] - p[0]) for i in (8, 12, 16, 20)]) / np.linalg.norm(p[9] - p[0])
            self.history.append((t, features))
            # Keep at least ten samples AND a quarter second at high frame rates.
            while len(self.history) > 10 and t - self.history[1][0] >= 250:
                self.history.popleft()
            fingers.update(features=features.tolist(), reason='calibration_required')
            if len(self.calibration) == 2:
                target = np.clip((features - self.calibration['fist']) / (self.calibration['open'] - self.calibration['fist']), 0, 1) * 180
                alpha = 1 if self.smoothing_ms == 0 else -math.expm1(-dt * 1000 / self.smoothing_ms)
                self.smoothed = target if self.smoothed is None else self.smoothed + alpha * (target - self.smoothed)
                fingers.update(valid=True, reason='ok', targets_0_180=self.smoothed.tolist(),
                               serial_preview=','.join(str(int(round(v))) for v in self.smoothed) + '\n')
            wrist['reason'] = 'neutral_required'
            if self.neutral is not None:
                axis = self.neutral[:, 1]
                lateral = self.current_frame[:, 0] - np.dot(self.current_frame[:, 0], axis) * axis
                if np.linalg.norm(lateral) > 1e-6 and np.dot(self.current_frame[:, 1], axis) >= .5:
                    lateral /= np.linalg.norm(lateral)
                    angle = math.atan2(np.dot(np.cross(self.neutral[:, 0], lateral), axis), np.dot(self.neutral[:, 0], lateral))
                    cfg = self.model.config
                    raw = cfg['wrist_servo_neutral_deg'] + math.degrees(angle) * cfg['wrist_twist_gain']
                    clipped = float(np.clip(raw, *cfg['wrist_servo_limits_deg']))
                    wrist.update(valid=True, reason='palm_twist_proxy', twist_rad=angle, servo_preview_deg=clipped, clamped=abs(raw-clipped)>1e-8)
                else:
                    wrist['reason'] = 'excessive_palm_tilt'
        else:
            self.history.clear()
            self.smoothed = None
        self.current_palm = None
        if self.last_depth_time is not None and t - self.last_depth_time > 1000:
            self.origin = None
        palm = (depth or {}).get('points', {}).get('Palm', {})
        xyz = [palm.get(k) for k in ('X_m', 'Y_m', 'Z_m')]
        if valid and palm.get('valid') and all(isinstance(v, (int, float)) and math.isfinite(v) for v in xyz) and xyz[2] > 0:
            self.current_palm = np.array(xyz)
            self.last_depth_time = t
            arm['reason'] = 'origin_required'
            if self.origin is not None:
                cfg = self.model.config
                delta = self.current_palm - self.origin
                target = np.array(cfg['origin_target_m']) + (np.array(cfg['camera_delta_to_robot']) @ delta) * cfg['translation_gain']
                solution = self.model.solve(target, self.last_joints)
                arm.update(reason=solution['reason'], camera_delta_m=delta.tolist(), target_m=target.tolist())
                if solution['valid']:
                    limit = cfg['max_joint_speed_rad_s'] * min(dt, .1)
                    joints = np.array(self.last_joints) + np.clip(np.array(solution['joints_rad']) - self.last_joints, -limit, limit)
                    self.last_joints = joints.tolist()
                    arm.update(valid=True, ik_solution_rad=solution['joints_rad'], joint_targets_rad=self.last_joints[:],
                               preview_m=self.model.forward(self.last_joints), last_preview_joints_rad=self.last_joints[:])
        return dict(schema_version=1, timestamp_ms=t, simulation_only=True, hardware_enabled=False,
                    model=self.model.config['name'], geometry_verified=False, fingers=fingers, wrist=wrist, arm=arm,
                    calibration=dict(fingers={k:v.tolist() for k,v in self.calibration.items()},
                                     wrist_neutral=None if self.neutral is None else self.neutral.tolist(),
                                     palm_origin_m=None if self.origin is None else self.origin.tolist()), message=self.message)
