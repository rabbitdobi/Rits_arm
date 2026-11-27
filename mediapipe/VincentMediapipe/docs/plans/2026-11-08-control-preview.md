# Camera-only Control Preview Implementation Plan

Goal: deliver the camera-only calibration, flexion and visual control prototype.
Spec: ../specs/2026-11-08-control-preview-design.md
Tech: existing Python, MediaPipe, OpenCV; no new dependencies.

1. Add `control.py`: pure geometry and session calibration/state. Tests first in
   `tests/test_control.py`: scale 200→160 at 40 cm gives 50 cm; reject tilted,
   missing, malformed and unstable data; assert finger flexion on known 3D shapes.
2. Integrate optional `--control-preview`, positive finite `--reference-cm`, C/R
   handling, exclusive JSONL, and preview rendering in main.py/effects.py. Keep
   base CSV contract. Test headless file input, loss output, rendered MP4 and
   command-line validation in test_cli.py.
3. Document usage and limitations. Run the full suite, diff checks, and actual
   recorded-hand offline smoke test. Decode a resulting MP4 and inspect a frame.

Review focus: no stale depth on lost/gap frames; nonfinite JSON disallowed; no
calibration through turned hands; no overwrite of recording files; no claims of
physical accuracy from synthetic geometry. Existing uncommitted MP4 work is part
of the user's current session and must be preserved. Work in place and do not
commit/push unrelated changes.

## Verification record

- Core, CLI, rendering and regression suite: 27 tests passed.
- Existing 6-second recorded-hand excerpt processed offline: 180 JSONL records,
  52 frames with valid finger/world geometry, no depth claimed without calibration.
  Final annotated MP4 has 180 frames at 30 FPS and decodable last frame; screenshot
  inspected for five finger bars and calibration status.
- Independent review completed. Fixed small-frame clipping and nonfinite derived
  distance with tests observed failing first; full 27-test suite passes afterward.
- Launcher is executable and passes zsh syntax validation; diff whitespace clean.
- Ruling: session-only known-distance calibration avoids silently reusing a
  reference from a different person/camera. Cost: user must press C each launch.
- Physical distance error and interactive camera calibration require the user's
  measured hand placement; not inferred from replay or synthetic tests.
