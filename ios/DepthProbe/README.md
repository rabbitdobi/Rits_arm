# Depth Probe — iPhone camera comparison

Small native iOS app for the Rits_arm experiment. It switches between the **front
TrueDepth** and **rear LiDAR** cameras, displays synchronized RGB video and the
median depth of the centered yellow box, and exports 10-second measurement CSVs.
No MediaPipe, motor commands, audio, network server, or video recording is included
in this initial phone experiment. The existing Python project is unchanged.

## Run on iPhone 16 Pro Max

1. Install full **Xcode** from the Mac App Store. Open it once, accept the license,
   and finish the iOS platform/components setup. Command Line Tools alone cannot
   build or install this app. Use a current Xcode supporting the phone's iOS version.
2. Connect the iPhone by USB, unlock it, and choose **Trust** if asked.
3. Open `DepthProbe.xcodeproj`. Select the **DepthProbe** target, then
   **Signing & Capabilities → Team**, and choose your Apple account's personal or
   development team. A paid membership is not required for personal on-device
   testing; free signing expires and can require rebuilding. If Xcode requests a
   unique bundle identifier, change `com.vinny.ritsarm.depthprobe` to your own.
4. Select your physical iPhone as the run destination. Enable **Settings → Privacy
   & Security → Developer Mode** on the phone if requested, restart and confirm.
   Let Xcode finish preparing the device, then click **Run**.
5. Allow camera access. A simulator has no TrueDepth/LiDAR; use the phone.

The app targets iOS 17+, portrait orientation, and exposes only supported depth
cameras. No account or credentials are embedded in the project.

## Compare cameras

- Fix **the same phone** in a stand. Keep lighting, target and distance consistent.
  The front and rear camera origins are in different places: measure from the
  active lens, or account for that offset when turning the phone around.
- Choose **Front TrueDepth** or **Rear LiDAR**. Video is unmirrored. Keep your palm
  filling the central yellow box; otherwise the reading can include background.
- Start with a stationary flat target, then a palm, then fingertips. Test repeated
  positions around 30/40/50/60 cm where valid data is available. These are test
  positions, not guaranteed operating-range specifications.
- Distance is a **spatial median**, not a temporal smoothing filter. The ROI is
  6% of image width × 6% of image height, sampled at the corresponding center of
  the synchronized registered depth image. At least **60%** of its pixels must
  contain positive finite depth. Invalid readings show a dash, not zero.
- **Jitter** is population standard deviation over up to the last 30 valid frames;
  a dropped/invalid frame or gap >0.5 seconds resets it. Low jitter does not prove
  correct distance. Neither the valid-pixel fraction nor jitter is a calibrated
  sensor confidence score.
- Depth filtering is **off for both cameras**. The selected depth resolution may
  differ; both actual resolutions appear on screen. The app displays Apple's
  reported `absolute`/`relative` depth accuracy classification. Conversion to
  meters does **not** turn relative accuracy into absolute accuracy.
- Enter an independently **measured reference distance in cm** if available.
  Otherwise leave it empty: depth/stability can still be compared, but accuracy
  cannot be claimed. A4 paper is 29.7 × 21 cm and can provide a rough length
  reference if kept straight; a ruler or tape is better for final measurements.
- Tap **Record 10-second test**, hold the target still, then **Share last CSV**.
  Export by AirDrop or save to Files. Camera switching is disabled during a test.
  Backgrounding/interruption saves the partial test; no frames means no test file.

CSV records every received synchronized collection during the test, including
invalid/dropped measurements. `depth_m`, `spatial_sd_m`, `temporal_sd_m` use meters;
`reference_cm` and signed `error_cm = depth_m * 100 - reference_cm` use centimeters.
Missing values are empty. The CSV includes the camera ID, camera name, phone
hardware model, iOS version, filtering setting, ROI fraction and reported accuracy.
`elapsed_s` is monotonic elapsed reception time since the test started.
CSV files stay in the app's Documents directory; Files/Finder file sharing is enabled.
No images are saved or transmitted. Sharing a CSV requires tapping Share.

## Development checks

```bash
# Works with Command Line Tools, no iOS SDK required.
zsh run-core-tests.sh

# Actual iOS compile; requires full Xcode. Unsigned, does not install.
zsh build.sh
```

The core checks exercise depth units, invalid-pixel rejection, padded pixel-buffer
ROI sampling, median, rolling jitter resets and CSV export. Swift frontend parsing
and plist validation do not replace an iOS build. Hardware sensor quality, permission
prompts, orientation and sign/install must be checked on the actual phone.

Implementation references: Apple's [LiDAR synchronized capture sample](https://developer.apple.com/documentation/avfoundation/capturing-depth-using-the-lidar-camera),
[TrueDepth streaming sample](https://developer.apple.com/documentation/avfoundation/streaming-depth-data-from-the-truedepth-camera),
and [AVDepthData units](https://developer.apple.com/documentation/avfoundation/avdepthdata).
