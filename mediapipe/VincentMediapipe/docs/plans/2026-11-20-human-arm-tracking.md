# Human arm tracking implementation

1. Test and implement pure Pose selection, metric shoulder/elbow/wrist sampling,
   geometry validation and CSV export in human_arm.py.
2. Add optional Pose runtime in main capture loop with exclusive logs/ownership;
   overlay and sensor table separated from robot simulation targets.
3. Add launcher and model provenance/docs; model downloaded from Google source.
4. Test using actual Pose inference on saved raw D455 samples, render inspect,
   full regressions and independent review. No motor commands.
