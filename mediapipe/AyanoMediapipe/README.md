# AyanoMediapipe

Ayano's original right-side hand tracker, kept separately from Vincent's version.
Tracking behavior is unchanged; only the shared model path was updated.
`pbl_mediapipe_terminal.txt` preserves the original terminal notes.

From the repository root, with the project dependencies installed:

```bash
source .venv/bin/activate
python mediapipe/AyanoMediapipe/main.py
```

Both versions use `mediapipe/models/hand_landmarker.task`.
Press **q** to close the camera window. For fingertip position/speed export and
glowing trails, use [VincentMediapipe](../VincentMediapipe/README.md).
