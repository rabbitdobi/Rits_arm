# Rits_arm

A PBL2 project connecting MediaPipe hand tracking to a fixed-base, five-finger robotic hand and arm through ROS.

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

Repository initialized for team collaboration. Implementation code, hardware details, ROS version, and setup instructions will be added as they are confirmed.
