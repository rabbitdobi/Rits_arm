# D455 missing-depth investigation — 2026-11-13

Inputs: `output/fingers-20261113-132108-878694.depth.csv`, matching control log,
metadata and MP4. Original recordings remain unchanged. This is a validity
investigation, not a distance-accuracy test.

## Existing run

1800 frames, 1637 with a detected right hand (90.9%). Valid palm depth in
1018 tracked frames (62.2%); 5692/8185 valid fingertip attempts (69.5%).

Across all joints and palm there were 12127 invalid tracked point measurements:

| Reason | Count | Meaning |
| --- | ---: | --- |
| center_hole | 11678 | Aligned depth at the projected landmark pixel was zero/nonfinite |
| sparse_depth | 231 | Valid center but less than 60% of patch valid |
| depth_edge | 96 | Local depth range exceeded boundary gate |
| invalid_pixel | 122 | Landmark outside image |

96.3% of invalid points are center holes. Relaxing the boundary gate cannot fix
the dominant failure. Missing values must not become zero distances or be filled
silently from background/old frames.

## Time-local behavior

Percentages use detected-hand frames only. Distance is median **valid sensor**
reading, not independently measured ground truth; invalid frames have no distance.

| Video seconds | Tracked frames | Valid palm | Median palm cm | Valid fingertips |
| --- | ---: | ---: | ---: | ---: |
| 5–10 | 116 | 27.6% | 32.0 | 40.7% |
| 10–15 | 150 | 40.0% | 32.2 | 38.0% |
| 15–20 | 150 | 89.3% | 39.5 | 88.5% |
| 20–25 | 150 | 93.3% | 40.6 | 92.9% |
| 25–30 | 150 | 42.7% | 42.2 | 70.0% |
| 30–35 | 150 | 62.7% | 51.9 | 75.5% |
| 35–40 | 149 | 94.0% | 48.8 | 87.1% |
| 40–45 | 150 | 94.0% | 47.9 | 88.7% |
| 45–50 | 150 | 94.7% | 50.5 | 96.0% |
| 50–55 | 150 | 34.7% | 39.1 | 55.5% |
| 55–60 | 150 | 4.0% | 31.8 | 28.0% |

Distance and pose deserve controlled testing, but their effects are confounded
with occlusion/illumination. This is not a universal working-range claim.

## Limits of old evidence

The old sampler returned before inspecting neighbors on center holes. Its zero
`valid_fraction` in those rows does not mean the whole patch was empty. Overlaid
MP4/colorized depth cannot reproduce numeric sampling, distinguish isolated holes
from missing regions, or isolate holes introduced by depth/color registration.

## Implemented diagnostics

- Measure neighborhood coverage/spread even for center holes, keeping XYZ null.
- Show valid fingertip count and raw-hole/sparse/boundary rejection counts.
- Optional `--depth-samples-every N`: same-frame original unmirrored BGR, aligned
  Z16, native pre-alignment Z16 and scale in NPZ; original normalized landmarks,
  sensor timestamps and measured points in JSON. Session metadata stores native
  depth intrinsics and depth-to-color extrinsics.
- Exclusive output creation and ownership restoration remain in place. No new
  filtering/recovery and no acceptance thresholds were introduced.

43 tests pass, including RED→GREEN tests for isolated-hole telemetry, null
measurements, native/aligned/color preservation, overwrite and CLI validation.
Independent review found no required diagnostic defect before the live run.

## Controlled capture

Run `D455诊断采样.command`. Keep camera and other participants' hands fixed.
Hold an open right palm about 50–60 cm away for 15 seconds, curl/extend slowly
for 15 seconds, then change distance slowly. This approximate placement tests
availability; use an independently measured reference for final accuracy checks.

Replay the original samples before deciding whether to change sensing settings,
registration or sampling. Any future recovered-depth method must be labeled
separately from raw depth and validated before robot use.

## New diagnostic run

`fingers-20261113-133103-863554`: user ended after 1016 frames (~34.17 seconds
of saved MP4), 937 with a detected hand. Valid palm: 800/937 (85.4%); valid
fingertips: 3984/4685 (85.0%). The user reported usually 4–5 valid fingertips
at the requested approximate distance. USB remains 2.1. Distance and pose were
not independently instrumented; this comparison is not a causal algorithm gain.

34 original samples saved aligned/native depth, unmodified color, actual scale
and normalized landmarks. Offline replay with recorded intrinsics and SDK
deprojection reproduced every classification and valid XYZ exactly (0 differences,
maximum coordinate error 0 m). This validates data consistency, not physical accuracy.

66 sampled point attempts had center holes; all 66 also had less than 60% valid
neighbors. None was an isolated center hole in an otherwise usable patch. Keep
these invalid instead of relaxing the center rule. This does not prove whether
each region was lost in stereo sensing, occlusion or registration; original
calibration/data is now available for that investigation.

MP4 start/end decode, original sample files belong to the normal user, and all
43 tests pass after capture. Raw evidence is in the session `.depth-samples/` and
matching CSV/metadata/MP4. Screenshot and summary JSON are in
`output/depth-analysis-20261113/`.

Next: fixed camera and independently measured distances, repeated to quantify
error and jitter. No robot-frame/motor-control accuracy claim yet.
