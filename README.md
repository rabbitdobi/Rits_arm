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
