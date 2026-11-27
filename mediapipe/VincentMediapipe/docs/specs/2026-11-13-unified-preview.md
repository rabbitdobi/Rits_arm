# Unified vision teleoperation preview

The user owns the full vision side: five fingers, wrist orientation and arm
position. Build one local simulation preview and a timestamped target log on top
of the working D455/MediaPipe tracker. Do not open a motor serial port, import a
hardware driver, or publish to a robot command topic.

Inputs: MediaPipe world landmarks (finger ratios/palm frame), current valid D455
palm XYZ (translation), frame timestamp. Keep missing values null. Preserve
ordinary camera/video tracking and existing CSV/MP4 contracts.

Finger open/fist calibration uses the median of at least 10 recent valid samples spanning
>=250 ms. Thumb feature is tip-to-pinky-base/palm length; other fingers use
tip-to-wrist/palm length, calculated in model world geometry. Open/fist span must
be >=0.1 for every finger. Output 0=fist,180=open in thumb/index/middle/ring/pinky
order, plus a five-value Arduino serial-string PREVIEW only. Never append a sixth
wrist value to existing firmware. Uncalibrated fingers expose no command.

Wrist is a palm-twist proxy, not anatomical wrist/forearm rotation. W sets a
neutral palm frame. Project the current lateral axis perpendicular to the neutral
longitudinal axis; signed twist maps to a separate neutral-90-degree servo
preview, limited to 30–150. Reject degenerate geometry and >60-degree change in
longitudinal direction. Its eventual hardware axis remains unassigned.

Space sets current valid palm XYZ as translation origin. Relative camera movement
maps through configurable signed axes and gains to a demo arm endpoint. Defaults:
robot forward=-camera Z, left=-camera X, up=-camera Y; gains 0.4; origin target
[0.25,0,0.13] m in a shoulder-origin model. This is an intuitive control mapping,
not calibrated camera-to-robot extrinsics. Reject outside-workspace, unreachable
and joint-limit-violating goals. Show the requested and rate-limited FK positions
separately. Lost/invalid depth yields no current arm target, never a zero target.
Require a fresh origin after >1 second of continuous depth loss.

The XM430 demo model follows Gesture-Arm-Demo's drawing convention and lengths:
upper=0.130,fore=0.124,tool=0.126 m; all zero upper points up, fore/tool forward.
Limits follow its arm.yaml. These are UNVERIFIED SIMULATION parameters, not proven
geometry of the user's assembled arm/attached five-finger hand. Fixed tool pitch
0; fourth arm joint is calculated by IK to maintain pitch. Both elbow branches
are checked and continuity is preferred. Joint motion is limited to 1 rad/s.

UI: unified panel with five command bars, wrist twist/servo preview, palm delta,
arm XYZ/joints and side/top model drawings. O=open, F=fist, W=wrist neutral,
Space=position origin, R=reset, Q=save/exit. Controls never actuate hardware.
Separate `.targets.jsonl` contains all three channels, validity/reasons,
calibration reference and explicit simulation-only status. Store model config in
the log. Optional original-frame samples include the unified packet for replay.

Verification: analytic FK/IK round trips, reach/limit failures, input/config NaN,
finger calibration/protocol direction, wrist twist/tilt, loss/reset/gaps,
timestamp monotonicity, output preservation, ordinary CLI regression. Replay
real saved original RGB/depth/landmarks through the full model offline, render
and inspect the unified preview, then offer the same interface on live D455.
