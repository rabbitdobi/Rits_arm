#!/bin/zsh
cd "$(dirname "$0")" || exit 1
if [[ ! -x .venv/bin/python ]]; then
  print 'Python environment is missing.'
  read '?Press Enter to close.'
  exit 1
fi
if [[ ! -f mediapipe/models/pose_landmarker_lite.task ]]; then
  print 'Pose model is missing. See mediapipe/VincentMediapipe/docs/human-arm-tracking.md.'
  read '?Press Enter to close.'
  exit 1
fi
mkdir -p mediapipe/VincentMediapipe/output
print 'HUMAN ARM TRACKING: shoulders, elbows and wrists, not robot target positions.'
print 'Keep your shoulders and entire arm inside the camera view; step back if needed.'
print 'Start roughly 1-1.5 metres away and slowly bend/straighten your RIGHT elbow.'
print 'Green = anatomical right arm. Blue = left arm. Preview is mirrored.'
print 'Keep wrists inside the grey guide; move BACK if the yellow hint says near edge.'
print '[hand] marks an assisted wrist location; depth is still read from this frame.'
print 'Sensor XYZ is in metres. Missing depth stays --; no calibration keys required.'
print 'Default colored skeleton is FILTERED; grey trace is RAW. V toggles the view.'
print 'XYZ table remains RAW; elbow angle shows raw and filtered. Filtering adds delay.'
print 'No motor commands. Q/Esc saves and exits. A configured frame limit also saves and closes normally.'
print 'Near-camera warning: move the whole arm BACK; do not reach toward the lenses.'
print 'Mac login password may be needed for USB access; input is hidden.'
arm_log="mediapipe/VincentMediapipe/output/human-arm-$(date +%Y%m%d-%H%M%S)-$$.log"
sudo "$PWD/.venv/bin/python" "$PWD/mediapipe/VincentMediapipe/main.py" --realsense --arm-tracking --no-trails --record --max-frames 9000 "$@" 2>&1 | tee "$arm_log"
arm_status=$pipestatus[1]
if (( arm_status != 0 )); then
  print 'Tracking did not finish. See the error above.'
else
  print '录制已正常结束，数据已保存。达到录制上限时，预览窗口会自动关闭。'
fi
read '?Press Enter to close.'
