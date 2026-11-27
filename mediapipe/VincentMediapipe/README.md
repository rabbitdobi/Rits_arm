# VincentMediapipe — Right-hand fingertip motion

Tracks the subject's **right hand** using MediaPipe handedness, regardless of
which side of the picture it occupies. The mirrored preview shows a skeleton,
five colored fingertip trails, coordinates, and speed. Press **q**, **Esc**, or
**Ctrl-C** to stop. This version exports motion data; it does not drive ROS or motors.

## Quick start

You need **Git**, **Python 3.10 or newer**, a camera, and an internet connection
for the first dependency installation. Tested with Python 3.13 on macOS; the
Windows commands below are provided but have not been tested on Windows.
The model is included in the repository, so no separate download is needed.

**Clone the repository once, following the [main README](../../README.md#get-the-code-clone-once-pull-for-future-updates).**
If you already have `Rits_arm`, skip cloning and use that existing folder.
Do not clone another copy inside `mediapipe` or `VincentMediapipe`.

Run **all commands below from the repository root**, the `Rits_arm` directory
containing `README.md`, `.git`, and `mediapipe/`. This README is inside a
subdirectory, but you do not need to change into that subdirectory to run it.

### First run — macOS / Linux

Open Terminal in the repository root and run. If `.venv` already exists, skip
the first command and activate the existing environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r mediapipe/VincentMediapipe/requirements.txt
python mediapipe/VincentMediapipe/main.py
```

### First run — Windows

Open **Command Prompt (cmd)** in the repository root and run. If `.venv`
already exists, skip the first command and activate the existing environment:

```bat
python -m venv .venv
.venv\Scripts\activate.bat
python -m pip install -r mediapipe/VincentMediapipe/requirements.txt
python mediapipe/VincentMediapipe/main.py
```

### Using the tracker

Allow camera access if prompted, then show your **right hand**. The preview
displays five fingertip positions, speeds, and colored glowing trails. Press
**q** or **Esc** while the preview window is focused to exit. **Ctrl-C** in the
terminal also stops the program and closes the CSV recording.

Every run automatically saves a CSV in `mediapipe/VincentMediapipe/output/`.
Speeds are in normalized screen units per second, **not centimeters per second**.

### Record a video demo

With the environment activated, run from the repository root:

```bash
python mediapipe/VincentMediapipe/main.py --record
```

Show your right hand to the camera. The program records the mirrored preview,
including the skeleton, colored fingertip trails, positions and speeds, to
`mediapipe/VincentMediapipe/output/demo-TIMESTAMP.mp4`. CSV data is saved as usual.
Press **q**, **Esc**, or **Ctrl-C** to stop and finish saving the MP4 before
opening it. Video recording is optional; without `--record`, only CSV is saved.
The video has no audio.

To choose a filename or another camera:

```bash
python mediapipe/VincentMediapipe/main.py --camera 1 --record mediapipe/VincentMediapipe/output/my-demo.mp4
```

Existing files are never overwritten. Camera recordings use 30 FPS, holding
frames when tracking runs slower so playback follows elapsed time. Video inputs
use the source FPS. `--headless --record` also saves the annotated video without
opening a preview window; `--no-trails` removes trails from the recording too.

If the wrong camera opens, or camera 0 is unavailable:

```bash
python mediapipe/VincentMediapipe/main.py --camera 1
```

To emit a JSON object for each frame on stdout while also saving CSV:

```bash
python mediapipe/VincentMediapipe/main.py --json
```

### Run again later

Open a terminal in your cloned `Rits_arm` directory. On macOS/Linux:

```bash
source .venv/bin/activate
python mediapipe/VincentMediapipe/main.py
```

On Windows Command Prompt:

```bat
.venv\Scripts\activate.bat
python mediapipe/VincentMediapipe/main.py
```

You only need to create the environment once. To get repository updates, stop
the tracker, enter the repository directory, and run:

```bash
git switch main
git pull --ff-only
python -m pip install -r mediapipe/VincentMediapipe/requirements.txt
```

Run the install command with the environment activated. If Git reports local
changes or diverging branches, keep your work and resolve that before updating.

### Camera and model setup

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

### Camera-only distance and finger control preview

This prototype can be developed without Arduino. In addition to the existing
fingertip tracking, it estimates palm distance from changes in apparent palm size
and shows five finger-flexion bars. It sends **no motor commands**.

On this Mac, double-click `开始距离校准.command` in the repository root to start
with control preview and MP4 recording. Or, with the Python environment active:

```bash
python mediapipe/VincentMediapipe/main.py --control-preview --reference-cm 40 --record
```

1. Measure **40 cm from the camera lens to the center of your right palm** (or use
   a different measured distance with `--reference-cm`). Face the palm toward the
   lens, keep it near the image center and keep all fingers visible.
2. Click the video window, switch to English input, and press **C**. Hold still
   until **ESTIMATED** appears: at least 20 stable tracked frames over 0.8 seconds
   are required. `HOLD STILL` means the collected palm sizes vary too much.
3. Move your hand slowly nearer/farther while keeping the palm facing the lens.
   `Palm Z estimate` is estimated camera-axis distance in cm; positive `delta`
   means farther than the reference. The distance is smoothed with a 100 ms time
   constant; loss or a gap over 250 ms clears the filter.
4. Curl/extend the fingers to move the colored bars. **0** means straight;
   **1** means roughly 90 degrees average flexion at the two measured joints.
   This is a geometry proxy, not a calibrated servo position. Thumb opposition
   and spreading fingers sideways are not measured.
5. **R** clears the distance calibration; **C** starts a new calibration.
   **Q / Esc / Ctrl-C** ends recording. Every launch needs a new calibration.

The reference uses median pixel distances between palm landmarks **5–17** and
**0–9**, combining their inverse scale ratios with a geometric mean. This is a
known-distance scale calibration, **not** full camera calibration. Changing user,
camera, zoom, crop or resolution requires recalibration. Keep camera settings
fixed; autofocus, hand movement off-axis, landmark errors, palm deformation and
rotation can still bias the result. A model-estimated palm-normal gate rejects
obvious tilts (frontality < 0.8); width/length ratio disagreement >20% also
suppresses depth. These gates do not guarantee accuracy or detect every rotation.
Missing/invalid measurements show `--` and are recorded as JSON `null`.

An additional `<CSV-stem>.control.jsonl` is saved next to the normal CSV, with
one object per frame. It includes `timestamp_ms`, `status`, `distance_cm`,
`delta_cm`, `flexion`, estimated `world_landmarks_m`, `frontality`, and calibration
reference spans/resolution. With `--json`, the usual output also gets a `control`
object. The existing fingertip CSV columns are unchanged. World landmarks are
MediaPipe's hand-centered 3D estimates, not camera-frame positions. Null distance
must never be interpreted as zero or as a command to keep moving.

`--headless --control-preview` exports finger/world data, but cannot accept C/R,
so distance remains uncalibrated. Ordinary input must be **unmirrored**; videos
recorded by this program are mirrored and contain overlays, so are not raw
calibration measurements. The MP4 includes the new control panel when enabled.

Before connecting hardware, measure at **30, 40, 50 and 60 cm**, with repeated
stationary readings and slight rotations. Compare estimates with a ruler and
record absolute error, jitter and invalid-frame rate. Synthetic tests and video
replay validate the software flow; **physical measurement accuracy is not yet
validated**. This method estimates palm depth only, not per-fingertip absolute
depth or calibrated robot-frame XYZ. ROS/Arduino protocols and motor calibration
remain a separate integration step.

### Existing motion recording

Every run creates a new CSV under the version's ignored `mediapipe/VincentMediapipe/output/` directory.
By default, only numeric motion data is recorded; `--record` also saves camera
images with the tracking overlay. Use a new filename for
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

## Unified fingers / wrist / arm simulation

See [统一控制预览与离线演示](docs/unified-preview.md). Use the root launcher
`查看离线控制演示.command` without a camera, or `开始统一控制预览.command`
when the D455 is available. All target values are preview/log output only.
The arm geometry is unverified; no Arduino/ROS commands are sent.

## Human shoulder/elbow/wrist tracking

Optional `--arm-tracking` enables Pose + same-frame D455 joint measurements.
See [人体手臂追踪说明](docs/human-arm-tracking.md), and use root launcher
`开始手臂三维追踪.command`. This measures human joints, separately from robot targets.
