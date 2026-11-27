# Depth Probe implementation and verification — 2026-11-09

The authorized first step is a local iPhone experiment comparing front TrueDepth
and rear LiDAR, before Arduino and before phone-to-Mac streaming. Native SwiftUI
uses AVFoundation's synchronized video/depth outputs, not a browser camera API.

## Decisions

- One serial capture queue owns format selection, lifecycle and measurements.
- A paired video/depth format is chosen at an available 15–30 FPS; video width
  near 1280 is preferred. Both outputs use portrait, unmirrored frames.
- Convert depth explicitly to DepthFloat32 (meters). Show centimeter values and
  Apple's reported relative/absolute accuracy class without promising accuracy.
- Measure a central 6% × 6% image patch with >=60% positive finite samples.
  The median is spatial only. Report temporal SD over up to 30 samples, resetting
  after invalid frames and >0.5 s gaps. UI hides depth when >1 s stale.
- A ten-second test exports every received synchronized collection, including
  missing depth. An optional independently measured reference produces signed
  error. Missing values remain empty. No network or image/video files are saved.
- CSVs have UUID filenames and camera/phone metadata. Backgrounding or switching
  captures finishes any partial test. Retry forces a new capture configuration.
- Existing Python work and local uncommitted files remain intact.

## Files

- `Sources/CaptureController.swift`: permission, synchronized buffers, metadata,
  frame publication and CSV test lifetime.
- `Sources/ContentView.swift`: camera selection, preview ROI, readout, test/share.
- `Sources/DepthStatistics.swift`: independently testable buffer sampling, robust
  statistics, temporal window and CSV conversion.
- `DepthProbe.xcodeproj`: shared app scheme, iOS 17+, personal automatic signing.

## Evidence and remaining validation

- Core checks were written before implementation. The test script now passes 18
  checks including units, invalid data, row stride, median, gaps and CSV escaping.
- Swift frontend syntax parse passes; project and Info plists pass validation.
- Existing Python suite still passes 27 tests.
- Independent review found no additional established SDK blocker after the
  CoreMedia subtype function correction. Retry was also made a forced restart.
- **iOS SDK compilation has not passed yet**: full Xcode is not installed. Core
  tests and parsing are not evidence that the UIKit/AVFoundation app compiles.
- **No device test yet**: no iPhone was present in USB inventory at verification.
  The user is installing Xcode and connecting their iPhone. Build, sign, launch,
  permission/lifecycle, synchronized ROI orientation, both cameras, CSV sharing
  and physical measurement accuracy must be verified afterward.
