#!/bin/zsh
cd "$(dirname "$0")" || exit 1
if [[ ! -x .venv/bin/python ]]; then
  print 'Python environment missing. Follow mediapipe/VincentMediapipe/README.md first.'
  read '?Press Enter to close.'
  exit 1
fi
print 'Hold your right palm facing the camera at 40 cm, then press C in the video window.'
print 'Hold still until ESTIMATED appears. R resets; Q stops and saves the video.'
.venv/bin/python mediapipe/VincentMediapipe/main.py --control-preview --reference-cm 40 --record "$@"
read '?Press Enter to close.'
