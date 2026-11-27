# Camera-only control preview

Build the agreed camera-only prototype before Arduino is available. Keep existing
tracking, CSV and MP4 recording unchanged unless `--control-preview` is enabled.

Use the existing RGB camera and known-distance palm-size calibration rather than
requiring an iPhone capture app or depth sensor. This estimates camera-axis palm
distance, not full calibrated XYZ or individual fingertip absolute depth. The
scale method assumes an approximately front-facing palm, fixed camera settings,
and the same participant. It is not a camera-intrinsic calibration.

Press C at `--reference-cm` (default 40 cm) to collect at least 20 stable samples
over at least 800 ms. Use palm width (5–17) and length (0–9) in pixel coordinates.
Median reference spans determine current distance by inverse geometric-mean
scale. Gate on estimated world-palm normal frontality >= 0.8, nondegenerate valid
landmarks, and reference/current span aspect agreement within 20%. Reject unstable
calibration (>10% span variation). Lost/invalid frames expose null distance,
never stale commands. Filters reset on loss/gaps. Calibration is session-local;
changing person/camera/settings requires restarting or pressing C again.

Use world landmark geometry for mean two-joint finger flexion: 0 straight,
1 approximately 90 degrees mean flexion, clipped to [0,1]. Thumb is a flexion
proxy and does not measure opposition. No servo ranges or ROS protocol assumed.

Show a five-finger bar preview, distance and status in the existing video window
and recordings. Save an additional exclusive `.control.jsonl` alongside CSV with
timestamps, quality state, distance, flexion, world landmarks and calibration
reference. Existing JSON gets an optional `control` object. Missing data is null.
R clears calibration. No hardware output.

Verify inverse scaling, rotation/loss/degenerate/NaN rejection, calibration
stability, frame gaps, flexion geometry, optional CLI behavior, real MP4 export and
offline processing of actual hand video. Physical distance accuracy and live key
interaction remain user-run checks with a ruler and camera.
