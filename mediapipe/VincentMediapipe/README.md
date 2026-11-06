# VincentMediapipe — Right-hand fingertip motion

Tracks the subject's **right hand** using MediaPipe handedness, regardless of
which side of the picture it occupies. The mirrored preview shows a skeleton,
five colored fingertip trails, coordinates, and speed. Press **q**, **Esc**, or
**Ctrl-C** to stop. This version exports motion data; it does not drive ROS or motors.

## Setup

Use Python 3.10 or newer (verified with Python 3.13 on macOS). From the repository:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r mediapipe/VincentMediapipe/requirements.txt
python mediapipe/VincentMediapipe/main.py
```

On macOS, allow the terminal app to access the camera. Try `--camera 1` if camera
0 is an iPhone or unavailable. MediaPipe supplies OpenCV; avoid installing
`opencv-python` alongside `opencv-contrib-python`.

The model is bundled at `mediapipe/models/hand_landmarker.task`; its default path is
resolved from the script's parent directory, so launching from another directory also works.
The original tracker is at `mediapipe/AyanoMediapipe/main.py`; both versions share the model. If it is
missing, download it from the official model storage:

```bash
curl -L --fail https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task -o mediapipe/models/hand_landmarker.task
```

## Recording and integration

Every run creates a new CSV under the version's ignored `mediapipe/VincentMediapipe/output/` directory.
Only numeric motion data is recorded, not camera images. Use a new filename for
each explicit `--csv` path; existing recordings are never overwritten.

```bash
# Preview and choose a recording path
python mediapipe/VincentMediapipe/main.py --camera 0 --csv mediapipe/VincentMediapipe/output/session-01.csv

# Machine-readable JSON Lines on stdout, CSV in parallel
python mediapipe/VincentMediapipe/main.py --json > mediapipe/VincentMediapipe/output/session-01.jsonl

# Repeatable offline processing (constant-frame-rate video)
python mediapipe/VincentMediapipe/main.py --video recording.mp4 --headless --json --csv mediapipe/VincentMediapipe/output/replay-01.csv

# Disable glow effects; other options are listed by --help
python mediapipe/VincentMediapipe/main.py --no-trails
```

Create the output directory first (`mkdir -p mediapipe/VincentMediapipe/output`) when redirecting stdout there before
the first run. Without `--json`, stdout is quiet. Startup/status/errors go to
stderr so they do not corrupt JSON Lines. End a headless camera run with Ctrl-C.

One JSON object is emitted per captured frame:

```json
{"schema_version":1,"timestamp_ms":100,"tracked":true,"handedness_score":0.96,"fingers":{"Thumb":{"x":0.2,"y":0.4,"vx":0.3,"vy":-0.4,"speed":0.5},"Index":{"x":0.3,"y":0.3,"vx":0.0,"vy":0.0,"speed":0.0},"Middle":{"x":0.4,"y":0.2,"vx":0.0,"vy":0.0,"speed":0.0},"Ring":{"x":0.5,"y":0.3,"vx":0.0,"vy":0.0,"speed":0.0},"Pinky":{"x":0.6,"y":0.4,"vx":0.0,"vy":0.0,"speed":0.0}}}
```

| Field | Meaning |
| --- | --- |
| `timestamp_ms` | Elapsed milliseconds from this run; strictly increasing. Camera timestamps use a monotonic clock; video timestamps use frame index / video FPS. |
| `tracked` | A right hand was found with handedness confidence >= 0.6. |
| `handedness_score` | Model confidence, or `null` when lost. |
| `x`, `y` | Smoothed fingertip coordinates matching the mirrored preview. Origin top-left, x increases right, y increases down. Nominal range 0–1; model predictions near edges may fall outside it. |
| `vx`, `vy` | Change in smoothed x/y per second, including direction. |
| `speed` | `sqrt(vx*vx + vy*vy)`, in normalized screen units per second. |

The five fingertips use landmarks 4, 8, 12, 16, and 20. The CSV has one row per
finger per tracked frame, with columns `schema_version,timestamp_ms,tracked,
handedness_score,finger,x,y,vx,vy,speed`. Lost frames produce one row with empty
finger/position/velocity columns. JSON loss looks like:

```json
{"schema_version":1,"timestamp_ms":133,"tracked":false,"handedness_score":null,"fingers":{}}
```

Velocities are `null` (empty CSV cells) on first detection, after loss, and after
a gap exceeding 250 ms. This avoids reporting a jump across missing data as real
motion. Position smoothing has a 60 ms time constant; velocities are differences
of those smoothed positions over elapsed time. Trails fade over 600 ms and clear
on loss/gaps; effects never alter exported data.

## Limits

- Coordinates and speed are **screen measurements, not centimeters or cm/s**.
  Changing camera distance, resolution aspect ratio, or moving the whole hand
  affects these measurements. x and y use different axis scales; speed is not
  a pixel distance or a physical motion magnitude.
- Smoothing reduces jitter but introduces a small delay; there is no calibrated
  joint angle or servo command in this output.
- Input must be an ordinary, unmirrored camera/video frame. The program mirrors
  only the preview/output coordinates. A camera that already mirrors its feed
  can invert handedness and should be configured to send raw frames.
- Intended for one participant. If multiple right hands are visible, the most
  confident is selected; identity continuity across people is not guaranteed.
- Offline video uses its reported constant FPS, not variable frame timestamps.
  Camera performance, lighting, occlusion and actual left/right behavior should
  still be checked with your own camera before ROS integration.

## Verification

```bash
python -m unittest discover -s mediapipe/VincentMediapipe/tests -v
```

The suite covers selection, mirrored coordinates, speed, smoothing, loss/gaps,
timestamp ordering, export, CLI launch/path handling and trail fading. The core
motion tests need only the Python standard library; display tests need the
installed vision dependencies.

References: [MediaPipe Python Hand Landmarker](https://developers.google.com/edge/mediapipe/solutions/vision/hand_landmarker/python),
[landmark coordinate definitions](https://developers.google.com/edge/mediapipe/solutions/vision/hand_landmarker).
