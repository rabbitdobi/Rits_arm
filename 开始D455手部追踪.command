#!/bin/zsh
cd "$(dirname "$0")" || exit 1
if [[ ! -x .venv/bin/python ]]; then
  print 'Python environment is missing.'
  read '?Press Enter to close.'
  exit 1
fi
mkdir -p mediapipe/VincentMediapipe/output
print 'D455 + MediaPipe: show your RIGHT hand around 60-80 cm from the camera.'
print 'Keep both small stereo lenses unobstructed. Start with a stationary open palm.'
print 'Left: mirrored tracking. Right: aligned depth, fingertip XYZ in meters and finger flexion.'
print 'No size calibration needed. Missing depth is --, never zero.'
print 'Q/Esc saves and exits; this test stops automatically after 1800 processed frames.'
print 'macOS USB access may request your Mac login password; characters are not displayed.'
tracker_log="mediapipe/VincentMediapipe/output/d455-tracker-$(date +%Y%m%d-%H%M%S).log"
sudo "$PWD/.venv/bin/python" "$PWD/mediapipe/VincentMediapipe/main.py" --realsense --control-preview --record --max-frames 1800 "$@" 2>&1 | tee "$tracker_log"
tracker_status=$pipestatus[1]
if (( tracker_status != 0 )); then
  print 'Tracking did not finish. See the error above.'
fi
read '?Press Enter to close.'
