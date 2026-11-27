# Human arm stabilization verification

- New separate visualization filter; raw XYZ, source reasons, geometry and CSV unchanged.
- Loss/invalid/gap/reset and disabled mode covered by pure tests; raw rejected geometry cannot turn valid through filtering.
- Full same-input dense-log comparison:1800frames; fixed static windows18–26s and44–52s.
- Source-switch step median25.064→2.430mm (10 adjacent pairs); angle STD1.814→1.255 and2.292→1.532deg.
- Extra midpoint-crossing delay133ms in35–40s transition; not a universal lag measurement.
- Static shared geometry coverage200/200 and199/201 unchanged. Filtering is not measurement accuracy improvement.
- Plot and original-frame sampled preview inspected; invalid wrist remains absent.
- Independent review found no required actionable issues; raw dictionaries/loss handling/paired metrics verified.
- Runtime raw/filtered toggle V, command-line smoothing parameter and bad argument checks included.
- Full unittest suite:79 tests passed after final code change; no motor/ROS commands sent.

Artifacts: output/arm-stabilization-20261120/
