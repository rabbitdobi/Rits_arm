# Right-hand fingertip motion

## Intent and scope
Improve the existing Python/OpenCV/MediaPipe tracker before ROS integration.
The user chose normalized screen coordinates and asked to proceed directly.
Track the subject's right hand using model handedness, show five fingertip
positions and velocities, export machine-readable data, and draw glowing trails.

## Approaches
Use normalized image coordinates (chosen): easy to inspect and integrate, but
not physical distances. World landmarks were considered: their hand-centered
origin cannot measure absolute hand travel. Centimeters require calibration
and are outside this version, as are ROS and actuator commands.

## Contract
- Output coordinates match the mirrored preview: x increases rightward, y downward.
- Use smoothed x/y and actual elapsed time; vx/vy are normalized axes per second;
  speed is sqrt(vx²+vy²). These are screen units, not meters or joint angles.
- One frame object has schema_version, timestamp_ms (elapsed, monotonic),
  tracked, handedness_score, and fingers keyed Thumb/Index/Middle/Ring/Pinky.
- A newly acquired hand has null velocities; lost frames have no finger data.
  Clear motion history on loss or gaps over 250 ms. Reject non-increasing time.
- Default CSV records all frames; --json emits equivalent JSON Lines on stdout.
  Diagnostics go to stderr. Never overwrite an existing recording.
- Fading trails use time rather than frame count; no stale trails connect across loss.
- Resolve the bundled model relative to the script, allow camera selection,
  support video/headless runs for repeatable verification, close resources on exit.
- Keep computational motion logic independent of camera/MediaPipe imports.

## Builder choices
Use an exponential position smoother with a 60 ms time constant. Confidence
threshold 0.6. Use MediaPipe VIDEO mode on raw frames; mirror only display/output.
Keep standard-library unit tests and document a real detector smoke run separately.
