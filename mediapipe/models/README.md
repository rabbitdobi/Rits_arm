# Shared models

`hand_landmarker.task` is the MediaPipe Hand Landmarker model used by both
`AyanoMediapipe` and `VincentMediapipe`. Keep a single copy here.

To download it again from the repository root:

```bash
curl -L --fail https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task -o mediapipe/models/hand_landmarker.task
```

`pose_landmarker_lite.task` enables optional human shoulder/elbow/wrist tracking.
Google MediaPipe Pose Landmarker Lite, float16, version1:

```bash
curl -L --fail https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/1/pose_landmarker_lite.task -o mediapipe/models/pose_landmarker_lite.task
```

Official task documentation: https://developers.google.com/edge/mediapipe/solutions/vision/pose_landmarker

A Full model was also evaluated via `--pose-model mediapipe/models/pose_landmarker_full.task`.
It did not improve depth availability on the current diagnostic captures, so Lite remains the default.
Optional Full source: https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_full/float16/1/pose_landmarker_full.task
