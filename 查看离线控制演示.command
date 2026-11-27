#!/bin/zsh
cd "$(dirname "$0")" || exit 1
if [[ ! -x .venv/bin/python ]]; then
  print 'Python environment is missing.'
  read '?Press Enter to close.'
  exit 1
fi
print 'Generating a SYNTHETIC demonstration. No camera or motor is accessed.'
print 'This shows control behavior, not real camera measurement accuracy.'
demo_output="$PWD/mediapipe/VincentMediapipe/output/unified-offline-$(date +%Y%m%d-%H%M%S)-$$"
"$PWD/.venv/bin/python" "$PWD/mediapipe/VincentMediapipe/unified_replay.py" --output "$demo_output"
if (( $? == 0 )); then
  print "Saved demo and target log: $demo_output"
  open "$demo_output/preview.mp4"
else
  print 'Demo failed. See the error above.'
fi
read '?Press Enter to close.'
