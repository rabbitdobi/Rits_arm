# Right-hand Motion Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans inline, task by task.

**Goal:** Track and export right-hand fingertip motion with glowing trails.
**Architecture:** Pure motion/export module, OpenCV trail renderer, camera/video CLI.
**Tech Stack:** Python, MediaPipe Tasks, OpenCV, NumPy, unittest.
**Spec:** mediapipe/VincentMediapipe/docs/specs/2026-11-06-right-hand-motion-design.md

## Global Constraints
Normalized mirrored x/y only; speed is not physical speed. No ROS or actuators.
First/acquired velocities null; clear on loss or gaps over 250 ms. Non-increasing
timestamps rejected. CSV never overwritten. Diagnostics must not pollute JSON.

## Review Focus
Hand labels versus screen location; reacquisition velocity spikes; recording
loss events; timestamps independent of inference speed; camera/model cleanup.

### Task 1: Motion and recording
Files: mediapipe/VincentMediapipe/motion.py, mediapipe/VincentMediapipe/tests/test_motion.py.
Interfaces: select_right_hand(result, min_score) -> index|None;
MotionTracker.update(landmarks|None, timestamp_ms, score=None) -> frame dict;
write_csv_frame(writer, frame), CSV_FIELDS.
- [x] Write unit tests for right-hand selection irrespective of x, mirrored
  coordinates, known 3-4-5 velocity, elapsed-time smoothing, loss/gap resets,
  invalid timestamps and CSV/JSON empty values.
- [x] Run unittest and confirm missing module/API failures.
- [x] Implement math and serialization; run full unittest suite green.

### Task 2: Display and runnable CLI
Files: mediapipe/VincentMediapipe/main.py, mediapipe/VincentMediapipe/effects.py, mediapipe/VincentMediapipe/tests/test_effects.py,
mediapipe/VincentMediapipe/tests/test_cli.py, mediapipe/VincentMediapipe/requirements.txt, mediapipe/VincentMediapipe/README.md, .gitignore.
Interfaces: FingerTrails.update(frame); FingerTrails.draw(image, timestamp_ms).
- [x] Write/run failing tests for visible trails, time expiry/loss clearing,
  command-line help from another directory, and refusal to overwrite CSV.
- [x] Add VIDEO-mode detection, CSV recording, --json, --camera, --video,
  --headless, --model and --no-trails; wire motion, display, cleanup.
- [x] Implement trails and document setup, units, schema, limitations and commands.
- [x] Run full suite plus offline detector/video smoke and inspect a preview image.

### Task 3: Review and upload
- [x] Review the branch against requirements; fix material issues with tests.
- [x] Verify git diff, full tests and smoke results; record practical limitations.
- [x] Commit and upload feature branch; open a pull request with validation details.

## Verification record
- 2026-11-06: 13 unittest checks passed under Python 3.13.9, MediaPipe 1.2.2,
  OpenCV 5.0.0.93, NumPy 2.5.4 in the project-local .venv. pip check passed.
- Real model processed 75 translated official hand-image video frames including
  10 blank frames: 75 valid JSON objects, 335 CSV rows; loss/reacquisition and
  first-sample null velocity verified. Earlier run also passed MediaPipe 1.1.1.
- Trail preview rendered and visually inspected. Independent read-only code
  review found no actionable issues. Real webcam behavior remains to be tested.
- Ruling: user requested direct implementation; use an in-place feature branch
  instead of introducing another checkout. Upload via GitHub connector and PR.
- Ruling: keep normalized x/y speeds; no physical-unit calibration or ROS.
