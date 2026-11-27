"""OpenCV preview of simulation targets; no device output."""
import cv2
import numpy as np


def draw_unified_panel(packet, model, height=480):
    panel = np.full((height, 580, 3), (25, 22, 20), dtype=np.uint8)
    scale = height / 480
    canvas = np.full((480, 580, 3), (25, 22, 20), dtype=np.uint8)
    def text(label, x, y, color=(210, 215, 220), size=.46):
        cv2.putText(canvas, label, (x, y), cv2.FONT_HERSHEY_SIMPLEX, size, color, 1, cv2.LINE_AA)
    text('SIMULATION ONLY - NO MOTOR OUTPUT', 12, 23, (70, 210, 255), .6)
    text('Unverified arm geometry | palm twist is an orientation proxy', 12, 45, size=.43)
    text('FIVE FINGERS  (0 closed / 180 open)', 12, 77)
    angles = packet['fingers']['targets_0_180']
    for i, name in enumerate(('Thumb', 'Index', 'Middle', 'Ring', 'Pinky')):
        y = 103 + i * 23
        text(name, 12, y)
        cv2.rectangle(canvas, (90, y-10), (210, y), (60, 60, 60), -1)
        if angles is not None:
            cv2.rectangle(canvas, (90, y-10), (90+int(120*angles[i]/180), y), (100, 210, 110), -1)
        text('--' if angles is None else f'{angles[i]:.0f}', 220, y)
    text(packet['fingers']['reason'], 12, 224, size=.4)
    wrist = packet['wrist']
    text('WRIST TWIST (separate preview)', 12, 255)
    text('Twist: --' if not wrist['valid'] else f"Twist: {np.degrees(wrist['twist_rad']):+.1f} deg", 12, 280)
    text('Servo: --' if not wrist['valid'] else f"Servo: {wrist['servo_preview_deg']:.1f} deg" + (' [limited]' if wrist['clamped'] else ''), 12, 303)
    text(wrist['reason'], 12, 326, size=.4)
    arm = packet['arm']
    text('ARM TARGET (metres)', 290, 77)
    target = arm['target_m']
    text('--' if target is None else 'XYZ: ' + ' '.join(f'{v:+.3f}' for v in target), 290, 100, size=.43)
    text(arm['reason'], 290, 122, (90, 200, 255), .42)
    # Show rate-limited FK separately from requested end point. Grey persists on invalid input.
    joints = arm['last_preview_joints_rad']
    points = model.forward(joints)
    color = (100, 220, 100) if arm['valid'] else (100, 100, 100)
    for title, axes, origin in (('SIDE X/Z', (0, 2), (320, 280)), ('TOP X/Y', (0, 1), (320, 412))):
        text(title + (' [held]' if not arm['valid'] else ''), origin[0]-25, origin[1]-110, size=.4)
        project = lambda p: (int(origin[0]+p[axes[0]]*490), int(origin[1]-p[axes[1]]*490))
        cv2.line(canvas, (origin[0]-15, origin[1]), (565, origin[1]), (65, 65, 65), 1)
        for a,b in zip(points, points[1:]):
            cv2.line(canvas, project(a), project(b), color, 4, cv2.LINE_AA)
        for p in points:
            cv2.circle(canvas, project(p), 4, (225, 225, 225), -1)
        if target is not None:
            cv2.drawMarker(canvas, project(target), (80, 180, 255), cv2.MARKER_CROSS, 13, 2)
    text('Joint preview (degrees)', 12, 357)
    values = arm['joint_targets_rad']
    for i in range(4):
        text(f'J{i+1}: ' + ('--' if values is None else f'{np.degrees(values[i]):+.1f}'), 12+(i%2)*125, 382+(i//2)*23)
    text('O open | F fist | W neutral | Space origin | R reset | Q quit', 12, 443, size=.43)
    text(packet['message'][:76], 12, 467, (100, 210, 240), .4)
    if scale != 1:
        return cv2.resize(canvas, (580, height))
    return canvas
