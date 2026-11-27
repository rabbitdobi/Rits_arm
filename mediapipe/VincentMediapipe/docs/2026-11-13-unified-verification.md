# Unified preview offline verification — 2026-11-13

No camera or motor was accessed for these checks.

- Full unittest suite: 59 tests, passed. Includes 60 FPS calibration, invalid/lost inputs, IK/FK, limits, log preservation and dense-sample replay.
- Main CLI: 30 existing video frames processed headlessly with unified + monocular preview, producing CSV, both JSONL logs, model config and annotated MP4.
- Synthetic demonstration: 240 input/log/video frames; five-finger targets valid on 216, wrist and arm valid on 215 after the scripted calibration events. All JSON is finite and hardware output is disabled.
- Recorded D455 replay: all 34 saved captures retained in video and log; hand features found on 27. No user calibration was recorded, so no command targets are generated. Playback is one sample per second; logs retain capture timestamps.
- Preview image inspected; both MP4 files reopened and frame count/dimensions checked (1220×480).
- Launcher shell syntax, Python compilation and git diff whitespace checks passed.
- Independent review found calibration-history duration, combined-preview keys and replay frame-dropping issues; fixed and checked.

Generated artifacts (ignored output directory):

- `output/unified-synthetic-final-20261113/`
- `output/unified-recorded-final-20261113/`
- `output/unified-cli-verification.*`

Not verified: live D455 performance after this change, depth accuracy, actual mounted arm geometry, servo directions, wrist actuator assignment or hardware communication. See unified-preview.md for the return-to-hardware checklist.
