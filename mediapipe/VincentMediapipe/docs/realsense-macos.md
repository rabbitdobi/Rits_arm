# D455 on this Apple Silicon Mac

This is the direct USB depth-camera route. It does not require Xcode, an iPhone
app, Arduino, or ROS. It is separate from the existing ordinary-camera tracker.

## Current local setup

- Camera: Intel RealSense Depth Camera 455 (D455), identified over USB.
- Official SDK: **librealsense v2.59.1**, commit
  `625279aa1fe903528a818f48746ee47c1b5fefd3`, built for arm64 with RSUSB.
- Source/build/install: `~/.local/share/rits-arm/realsense/`.
- Python module installed in this repository's `.venv` (Python 3.13).
- CMake and pybind11 were installed in the virtual environment; SDK compilation
  uses its own pinned pybind11 dependency. No Homebrew or full Xcode is required.
- SDK telemetry/update checks, GUI tools, IMU tests, and rosbag2 build are disabled.
  Camera firmware has not been modified.

Normal-user enumeration on this machine fails with `cannot access depth sensor`.
The official macOS instructions document administrator access for RSUSB on
macOS 12+. The launcher prompts for that access in Terminal, not in chat.

## D455 with MediaPipe

Run **开始D455手部追踪.command**, or from a Terminal at repository root:

```bash
sudo "$PWD/.venv/bin/python" "$PWD/mediapipe/VincentMediapipe/main.py" --realsense --control-preview --record --max-frames 1800
```

The left panel tracks the right hand; the right shows aligned depth, fingertip XYZ
in meters, valid-tip count and missing-depth reasons. This mode prefers the largest
right hand to reduce background-hand selection. It does not guarantee identity;
keep other participants' hands outside the image. Ordinary-camera selection is
unchanged.

XYZ is in the unmirrored D455 color optical frame (+X right,+Y down,+Z forward).
Preview mirroring does not negate metric X. Sampling uses current unsmoothed,
unmirrored landmarks, a valid center and >=60% coverage in a clipped 3×3 patch.
Patch range must be <=max(3 cm,5% of median). The SDK deprojects median depth at
the landmark ray. These are visible-surface approximations at model landmark
locations, not measured internal joint centers. No depth holes or old values are
silently filled. Uniform background mistaken for a landmark is still a limitation.

The legacy CSV retains normalized screen positions/velocities, not meters or m/s.
`.depth.csv` exports all 21 joints plus the palm proxy with metric XYZ and quality
fields; a lost hand generates an empty-point row. `.depth.json` stores camera
calibration/units. `.control.jsonl` stores model-based flexion and sensor palm Z.
Flexion still comes from MediaPipe world landmarks, not sensor depth. `--json`
also adds a `depth` object. MP4 includes both panels. No Arduino/ROS output exists.

## Reproducible missing-depth evidence

Run **D455诊断采样.command** to add `--depth-samples-every 30`. It creates a new
`<CSV-stem>.depth-samples/` folder, saving every 30th processed frame:

- `000000.npz`: original unmirrored/unannotated `color_bgr`, aligned `depth_z16`,
  pre-registration `native_depth_z16`, actual `meters_per_unit`.
- `000000.json`: original normalized landmarks, timestamp, hand confidence and
  the same-frame depth measurements and sensor timestamps/frame numbers.
- Session `.depth.json`: native/color intrinsics, distortion and depth-to-color
  extrinsics. Native and aligned pixels cannot be compared at identical indices
  without accounting for calibration.

This optional mode saves camera images locally and uses extra storage. It is off
in the ordinary tracking launcher. Center-hole rows now include measured neighbor
coverage/spread while XYZ remains null. See the
[2026-11-13 investigation](2026-11-13-depth-investigation.md).

## Standalone diagnostic

Double-click **开始D455测试.command** at repository root. Enter the Mac login
password in Terminal if prompted; characters are not echoed. It opens color on
the left and depth **aligned to color** on the right. Both are unmirrored.

Start with the palm around **60 cm** from the camera, centered in the yellow
box. The nearest valid distance depends on depth resolution and configuration;
the earlier 30–40 cm monocular tests must not be assumed valid for this camera.
Move slowly nearer/farther and inspect invalid-depth holes, especially along
fingertip/background boundaries. Press **Q/Esc** in the video window to save.
Otherwise capture ends after 1800 processed frames (not a guaranteed 60 seconds).

For a short headless capture from an ordinary Terminal at repository root:

```bash
sudo "$PWD/.venv/bin/python" "$PWD/mediapipe/VincentMediapipe/realsense_probe.py" --frames 90
```

The probe requires exactly one D455. It requests 640×480 color BGR8 and depth
Z16 at 30 FPS, drops 30 startup frames, then aligns depth using `rs.align(color)`.
There are no added spatial/temporal/hole-filling filters. The center 6% × 6%
patch requires >=60% nonzero finite pixels; otherwise distance is missing.
Raw values are multiplied by the **actual `get_depth_scale()`** in meters/unit,
not an assumed millimeter conversion. The on-screen value is displayed in cm.

A new ignored `output/realsense-TIMESTAMP/` directory contains:

- `color.png`: last captured color image.
- `aligned-depth.png`: SDK-colorized aligned depth, **not metric raw values**.
- `preview.png`: annotated side-by-side diagnostic view.
- `aligned-depth-raw.npz`: aligned `depth_z16` and `meters_per_unit` for numeric use.
- `measurements.csv`: every processed frame's SDK color/depth timestamps, elapsed
  monotonic time, center median meters, center validity and full-frame validity.
- `metadata.json`: camera firmware, USB connection type, actual scale and aligned
  camera intrinsics/distortion for later deprojection.

Outputs are never overwritten. Files created by this elevated probe are restored
to the invoking user's ownership. A timeout/error can leave a partial directory;
Q/Esc is the normal way to finish and save. Terminal logs stay in `output/`.

This confirms capture/alignment and data availability, **not measurement accuracy**.
The displayed center distance may describe the background if the palm doesn't
fill the patch. The integrated tracker above now consumes this camera; accuracy
validation, robot-frame calibration and motor integration remain separate steps.

## Rebuild if needed

Use the existing local source and build directories. The CMake cache records the
complete configuration. Important flags are `FORCE_RSUSB_BACKEND=ON`,
`BUILD_PYTHON_BINDINGS=ON`, `BUILD_EXAMPLES=OFF`, `BUILD_GRAPHICAL_EXAMPLES=OFF`,
`BUILD_GLSL_EXTENSIONS=OFF`, `BUILD_TOOLS=OFF`, `BUILD_LEGACY_PYBACKEND=OFF`,
`BUILD_ROSBAG2=OFF`, `ENABLE_STATS=OFF`, `CHECK_FOR_UPDATES=OFF`, and
`ENABLE_AI_ASSISTANT=OFF`. `Python_EXECUTABLE` and `PYTHON_EXECUTABLE` point to
the repository's `.venv/bin/python`; `PYTHON_INSTALL_DIR` points to its
`site-packages/pyrealsense2`. `CMAKE_INSTALL_PREFIX` is the local SDK install
directory, and `CMAKE_INSTALL_RPATH` points to that directory's `lib` so Python
can load the shared library without global environment changes.

## First actual camera run — 2026-11-11

The user confirmed the color/depth windows appeared. The completed probe saved
1800 synchronized frames in 60.33 seconds at 640×480. Raw depth is uint16 with
sensor-reported scale 0.0010000000474974513 meters/unit. Center-patch depth was
valid in 836/1800 frames; observed median values ranged from 0.294 to 0.702 m.
These are sensor readings, not accuracy against an independently measured ruler.

SDK reports firmware 5.15.1.55 and USB type **2.1** (USB 2 operation). Color/depth
capture worked in the requested mode, but USB 3 should be checked before increasing
resolution or adding streams. The final image shows substantial hand-region holes
with a near hand. Holes must remain invalid and must not be interpreted as zero
distance. Test a stationary palm farther away before trying fingertip control.

Files: `output/realsense-20261111-133201-026373/`. The saved raw array shape is
480×640, every captured frame has a CSV row, and output ownership was restored
to the ordinary user. All 30 Python tests pass, including three new depth-unit
and invalid-depth tests. Independent code review found no required defects.

```bash
.venv/bin/cmake --build "$HOME/.local/share/rits-arm/realsense/build-2.59.1" --parallel 6
.venv/bin/cmake --install "$HOME/.local/share/rits-arm/realsense/build-2.59.1"
.venv/bin/python -c 'import pyrealsense2 as rs; print(rs.__version__)'
.venv/bin/python -m unittest discover -s mediapipe/VincentMediapipe/tests -v
```

The SDK's current macOS release does not support its GUI Viewer. This probe uses
OpenCV for the live view. See [official macOS setup](https://github.com/realsenseai/librealsense/blob/master/doc/installation_osx.md)
and [official align-depth-to-color example](https://github.com/realsenseai/librealsense/blob/master/wrappers/python/examples/align-depth2color.py).
