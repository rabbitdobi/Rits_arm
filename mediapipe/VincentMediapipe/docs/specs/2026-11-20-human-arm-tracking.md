# Human shoulder/elbow/wrist tracking

User clarified that “improve arm detection” means identifying the full human arm,
not smoothing the existing palm-to-robot mapping. Add optional MediaPipe Pose
alongside the existing hand tracker, in the same raw RGB/D455 capture loop.

Approach: model-estimated world coordinates alone could work without depth but
would not be direct camera-relative metric measurements. Use Pose image landmarks
plus same-frame aligned D455 depth instead, as in the existing hand pipeline.
Track both shoulders, elbows and wrists; display the right arm prominently.
No new robot control mapping: human measurements and robot targets remain separate.

Pose confidence gates visibility/presence at0.6; normalize coordinates unmirrored.
Use existing conservative depth sampling (valid center, >=60%coverage, edge check).
Missing/occluded/outside pixels remain null; no guessed depth, temporal filling,
or mapping of human anatomical angles directly to unverified XM430 geometry.
Only calculate elbow flexion and shoulder-relative wrist XYZ when the same frame
has all three metric joints and plausible broad segment lengths (0.10–0.65m).
This is a sanity check, not accuracy calibration. Select largest visible pose,
intended for one foreground participant, no identity lock.

Optional --arm-tracking, --pose-model. Separate .human-arm.jsonl and
.human-arm.csv; same timestamps, exclusive paths, sudo ownership restoration.
Original diagnostic sample JSON includes human_arm when enabled. Existing hand
CSV, optional unified target log and ordinary camera behavior remain compatible.
Webcam/video can show 2D arm skeleton, with sensor XYZ absent.

Preview: shoulder-elbow-wrist overlay with visible-only connections; arm mode
replaces fingertip table on the D455 depth view with human right-arm metric table,
elbow flexion, segment lengths, completeness and reasons. Dedicated launcher
starts D455 human-arm tracking with recording for up to9000 processedframes;
shoulder and elbow must fit in image, user may need to stand farther back.

Verify: known synthetic depth/calibration and90/straight elbow, confidence, holes,
loss/out-of-range, mirrored overlay not metric XYZ, log output/no-overwrite;
offline original RGB+depth samples via actual Pose inference, annotated artifacts;
existing full suite. Live camera test only when connected and user ready.

2026-11-20 follow-up: add rolling right-arm raw sample availability to help
verify distance/framing improvements live. Window≤2000ms, warmup≥10frames and
≥1000ms, displayed span is actual observed duration. Gap>250ms resets window,
not session totals. Report raw depth completeness separately from raw geometry;
never label this as accuracy. Per-frame independent quality snapshot and normal
exit totals, no new geometry/depth fallback or motor behavior.
