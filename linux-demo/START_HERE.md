# Linux Demo Quick Start

First, check that the **D455 reports a stable palm depth** and **DYNAMIXEL Wizard detects all four motors**. Once both checks pass, teach the arm its reference poses and test motion tracking.

## 1. Get the demo code

If the repository is not on the Linux machine yet, open a terminal in your projects folder and run:

```bash
git clone -b linux-teleop-demo https://github.com/rabbitdobi/Rits_arm.git Rits_arm_linux
cd Rits_arm_linux/linux-demo
```

If you already cloned the repository and are on the `linux-teleop-demo` branch, run `git pull --ff-only` in the existing checkout, then open the `linux-demo` directory. Run the commands below from that directory.

## 2. Connect the D455 and open the preview

For the first run, create a virtual environment and install the dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r mediapipe/VincentMediapipe/requirements.txt pyrealsense2 dynamixel-sdk
```

If the dependencies are already installed, run `source .venv/bin/activate` in each new terminal.

Connect the D455 directly to the Linux machine using a USB 3 data cable. Then run:

```bash
python mediapipe/VincentMediapipe/main.py --realsense --no-trails
```

When the color and aligned depth views appear, hold your right hand about **65–90 cm** from the camera and check that the palm depth reading is stable. Press **Q** to exit. This command previews the camera and tracking data without moving the arm.

## 3. Scan the arm with DYNAMIXEL Wizard

1. Check that the U2D2 is connected to the Linux machine and that the four motors are powered through the arm's existing power supply.
2. Open **DYNAMIXEL Wizard**, scan, and record the Linux serial port, baud rate, and motor IDs. The demo expects **Protocol 2.0 at 1 Mbps** and IDs **001, 002, 003, and 004**, in order from the base to the wrist pitch joint.
3. Close Wizard after the scan to free the serial port for Python. If the results differ from the expected settings, record them and check the motor configuration before continuing.

To see which devices Linux detected, run:

```bash
lsusb -t
ls -l /dev/serial/by-id/
```

## 4. After both checks pass

Follow [Section 3 of the full guide](README.md#3-只读检查并示教机械臂) to run a read-only motor check, then capture the neutral pose and six small offsets. For the first motion test, run the four-axis arm by itself. Arduino wrist control and ROS 2 integration can follow once the arm is working.

If a step fails, copy the full terminal error or capture a screenshot of the D455 preview or the Wizard scan.
