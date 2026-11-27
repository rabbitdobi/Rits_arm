# Unified preview implementation

Spec: ../specs/2026-11-13-unified-preview.md

1. Add configurable demo arm geometry and FK/IK (`arm_simulation.py`, JSON config).
   Tests first: zero pose, reachable roundtrip, unreachable/limits/NaN. Preserve
   model provenance and unverified status.
2. Add `unified_control.py`: finger calibration, palm twist, relative translation,
   state/loss handling and packet construction. Pure tests before implementation.
3. Integrate optional CLI and `.targets.jsonl` with main.py; add a separate preview
   panel and launcher. Maintain base CSV and ordinary camera/video behavior.
4. Add offline original-sample replay runner and saved-data demonstration. Run all
   tests, inspect renders and logs, request independent review, fix findings.

Work in the current repository to preserve this session's accumulated edits.
No hardware/network command output; no merge/push. Real arm dimensions and which
actuator receives palm twist remain hardware integration work, not assumed facts.
