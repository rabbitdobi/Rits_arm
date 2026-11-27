# Rits_arm

## Get the code: clone once, pull for future updates

Install [Git](https://git-scm.com/downloads) first. Open Terminal on macOS/Linux,
or Command Prompt / Git Bash on Windows.

### First time: clone this repository

Go to the directory where you want to keep the project, then run:

```bash
git clone https://github.com/rabbitdobi/Rits_arm.git
cd Rits_arm
```

`git clone` creates a new `Rits_arm` folder and downloads the repository into it.
You only need to do this once. It does **not** update an existing clone; if a
non-empty `Rits_arm` folder already exists at that location, cloning there fails.

Next, follow the [setup and run instructions](mediapipe/VincentMediapipe/README.md#quick-start)
to install Python dependencies and start the tracker.

### Already cloned: update your existing code

When new changes have been merged into GitHub's `main` branch, stop the tracker
and open a terminal in your existing `Rits_arm` folder, then run:

```bash
git switch main
git pull --ff-only
```

If the terminal is in the folder containing `Rits_arm`, run `cd Rits_arm` first.
`git pull` updates files **inside the existing clone**; it does not create a new
folder. You do not need to clone again after each change. Changes on a feature
branch or an unmerged pull request are not included in `main` yet.

If dependencies have changed, activate your existing Python environment and run:

```bash
python -m pip install -r mediapipe/VincentMediapipe/requirements.txt
```

If Git reports local changes or diverging branches, save your work before
resolving the update. Do not delete your clone or discard your own edits just to
get the latest code.

## About this project

A PBL2 project connecting MediaPipe hand tracking to a fixed-base, five-finger robotic hand and arm through ROS.

## Try VincentMediapipe

Want to run the right-hand tracker on your own computer? Start with the
[installation and usage guide](mediapipe/VincentMediapipe/README.md#quick-start).
It covers cloning this repository, macOS/Linux and Windows setup, camera
selection, CSV/JSON output, and running again later.

The hand landmark model is included. You need Git, Python 3.10 or newer, and a
camera. This version displays fingertip positions, speeds and glowing trails;
it does not require ROS or a robotic hand.
Add `--record` when starting the tracker to save an MP4 demo with the tracking
overlay. See the [video recording guide](mediapipe/VincentMediapipe/README.md#record-a-video-demo).

For the camera-only prototype, run with `--control-preview --reference-cm 40`.
Place your palm at the measured reference distance, press C to calibrate, then
preview estimated palm distance and finger flexion without Arduino. On macOS,
`开始距离校准.command` starts this mode with MP4 recording. See the
[calibration guide and limits](mediapipe/VincentMediapipe/README.md#camera-only-distance-and-finger-control-preview).

## RealSense D455 depth experiment

The direct USB route uses a D455 and the local Python environment, without an
iPhone or full Xcode. Run `开始D455测试.command` to inspect color and aligned
depth and save a numeric depth diagnostic. `开始D455手部追踪.command` integrates
MediaPipe and metric XYZ export; `D455诊断采样.command` also saves original-frame
evidence for investigating depth holes. See the [D455 guide](mediapipe/VincentMediapipe/docs/realsense-macos.md)
for macOS USB permissions, outputs and measurement limits. No motor output exists.

## iPhone depth experiment

The native [Depth Probe app](ios/DepthProbe/README.md) is a separate experiment to
compare front TrueDepth and rear LiDAR on the same iPhone. It displays synchronized
video and center-region depth and exports 10-second CSV tests. Full Xcode and a
physical depth-capable iPhone are required; this is not yet connected to MediaPipe,
ROS or the robotic hand. See its README for installation and measurement limits.

## Project Goal

Develop a prototype that follows a user's finger movements and demonstrates controlled grasping of lightweight objects. The proposed application is remote handling of delicate objects at a fixed workstation.

## Team Responsibilities

| Team member | Responsibility |
| --- | --- |
| Ayano | MediaPipe hand tracking and tracking output |
| Shota | ROS integration with the robotic hardware and motor control |
| Vinny | Connection between MediaPipe and ROS, data conversion, and system integration |

## System Overview

```text
Camera -> MediaPipe hand tracking -> Integration bridge -> ROS -> Robotic hand
```

The team will agree on the tracking output, ROS input, finger order, value ranges, update rate, and behavior when tracking is lost before implementing the bridge.

## Development Milestones

1. Agree on the interface between MediaPipe and ROS.
2. Test the connection using simulated finger commands.
3. Connect live tracking output to the ROS input.
4. Calibrate finger movement and test the integrated system.
5. Demonstrate grasping and releasing a lightweight object, such as an empty paper cup.

## Optional Extensions

- Mount and integrate the hand with the fixed-base robotic arm.
- Add grip sensing and feedback if supported by the hardware.
- Compare grasping performance with and without feedback.

## Current Status

VincentMediapipe can track the right hand and export fingertip positions and
speeds. See the [MediaPipe directory](mediapipe/README.md) for the separate
versions and shared model. ROS and hardware integration are still in development.

## 统一控制预览（离线可运行）

- 没有摄像头：双击 `查看离线控制演示.command`。生成并播放合成手部输入的演示视频，保存三路目标日志；不连接摄像头或电机。
- D455 接回后：双击 `开始统一控制预览.command`。五指、手腕扭转和机械臂位移在一个窗口中预览，并录制 MP4。
- 校准、输出单位、离线重放和限制见 [统一控制说明](mediapipe/VincentMediapipe/docs/unified-preview.md)。

机械臂模型尚未实物校准；当前版本不发送 Arduino 或 ROS 控制命令。

## 人体肩、肘、腕三维追踪

双击 `开始手臂三维追踪.command`，用 MediaPipe Pose + D455 同帧深度检测人的整条手臂。
它与原来的掌心控制模拟机械臂分开；不需要校准按键，需让肩膀到手腕完整进入画面。
操作、缺失处理与局限见 [人体手臂追踪说明](mediapipe/VincentMediapipe/docs/human-arm-tracking.md)。
