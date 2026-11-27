# Human arm visualization stabilization

User authorized continuing iteration after static test. Measured source-switch
wrist steps around25mm median vs3.4mm on other adjacent samples in selected
static intervals. Inputs and raw anatomical accuracy remain uncalibrated.

Add a separate filtered visualization, never overwrite points/arms/CSV raw XYZ.
Time-based EMA80ms, with180ms time constant for240ms after a landmark-source
switch. Zero smoothing disables both. This reduces sudden source transitions,
not their underlying position bias; sustained model offsets remain.

Only current-valid finite XYZ enter the filter. Clear per-joint state immediately
on invalid input; reset after gaps>250ms. No missing-value filling. Raw rejected
segment geometry clears that arm's filter. Filtered angles require valid current
raw geometry AND valid filtered geometry. Keep per-point source/reset/alpha
metadata and settings in JSON. No robot target mapping/ROS/motor output changes.

Overlay: muted raw skeleton plus colored filtered skeleton by default; V toggles
raw/filtered view. Right-hand table keeps RAW XYZ and shows raw vsfiltered elbow
angle. Video/UI labels indicate filtering. Original hand/body outputs preserved.

Offline compare entire dense captured1800frame log, including original sources,
not re-inference on sparse samples. Use same preselected18–26s and44–52s video
intervals, report coverage, adjacent-step changes and angle variation. Report
movement response/lag separately using full transition sequence; no accuracy
claim. Tests first: time/rate behavior, source jump, fast motion, invalid/loss/gap,
disabled config, raw immutability and original geometry rejection. Inspect renders,
full regression suite and independent review before live retest.
