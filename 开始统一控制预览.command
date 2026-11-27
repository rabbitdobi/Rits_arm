#!/bin/zsh
cd "$(dirname "$0")" || exit 1
if [[ ! -x .venv/bin/python ]]; then
  print 'Python environment is missing.'
  read '?Press Enter to close.'
  exit 1
fi
mkdir -p mediapipe/VincentMediapipe/output
print 'SIMULATION ONLY: no commands are sent to Arduino or the arm.'
print 'Show your RIGHT hand at 50-80 cm; keep the stereo lenses clear.'
print 'Hold OPEN for one second, press O. Hold a FIST for one second, press F.'
print 'Hold a neutral palm and press W for wrist twist.'
print 'Keep a valid palm depth, press SPACE to set the arm motion origin.'
print 'Move slowly. R resets all calibration. Q/Esc saves and exits.'
print 'Grey arm drawing = held preview, not a current target.'
print 'Mac login password may be needed for USB access; input is hidden.'
preview_log="mediapipe/VincentMediapipe/output/unified-preview-$(date +%Y%m%d-%H%M%S).log"
sudo "$PWD/.venv/bin/python" "$PWD/mediapipe/VincentMediapipe/main.py" --realsense --unified-preview --record --max-frames 1800 "$@" 2>&1 | tee "$preview_log"
preview_status=$pipestatus[1]
if (( preview_status != 0 )); then
  print 'Preview did not finish. See the error above.'
fi
read '?Press Enter to close.'
