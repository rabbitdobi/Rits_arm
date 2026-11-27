#!/bin/zsh
cd "$(dirname "$0")" || exit 1
if [[ ! -x .venv/bin/python ]]; then
  print 'Python environment is missing.'
  read '?Press Enter to close.'
  exit 1
fi
mkdir -p mediapipe/VincentMediapipe/output
print 'D455 USB access on this macOS requires administrator access.'
print 'Enter your Mac login password if prompted. Password characters are not displayed.'
print 'Show your palm to the D455, starting around 60 cm away.'
print 'The window shows color on the left and aligned depth on the right.'
print 'Press Q in the video window to finish and save; otherwise the test captures 1800 frames.'
probe_log="mediapipe/VincentMediapipe/output/d455-terminal-$(date +%Y%m%d-%H%M%S).log"
sudo "$PWD/.venv/bin/python" "$PWD/mediapipe/VincentMediapipe/realsense_probe.py" --preview --frames 1800 "$@" 2>&1 | tee "$probe_log"
probe_status=$pipestatus[1]
if (( probe_status != 0 )); then
  print 'The D455 test did not finish. The log above explains the error.'
fi
read '?Press Enter to close.'
