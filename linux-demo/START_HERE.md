# Linux Demo Quick Start

Run the live arm demo with [`linux_teleop.py run`](#5-run-the-arm-mapping). It uses the D455 to measure your palm position in 3D and maps changes in that position to the four Dynamixel joints using poses taught on the robot. The camera preview in Step 2 checks the D455 before the live test.

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

## 4. Check and teach the arm

Use the U2D2 serial port found in Step 3. Replace `/dev/ttyUSB0` below if Wizard showed a different port.

```bash
ARM=/dev/ttyUSB0
python xm430_arm_demo.py --port "$ARM"
```

The command reads the motor configuration and positions. Confirm it reports all four motors and that torque is off on each. Secure the base, clear the arm's path, and support it before teaching.

```bash
python linux_teleop.py teach --arm-port "$ARM" --calibration bench.json
```

Follow the prompts to record the neutral pose and six 20 mm offsets around it, one in each direction along the camera's X, Y, and Z axes. Return the arm to the original neutral pose at the end. The script saves the poses to `bench.json`. Use a new filename if you need to teach again, and use that same filename when you run the demo. See [the full guide](README.md#3-只读检查并示教机械臂) for the direction conventions.

## 5. Run the arm mapping

With the arm at the taught neutral pose, its path clear, and the motor power cutoff within reach, run:

```bash
python linux_teleop.py run --arm-port "$ARM" --calibration bench.json
```

1. Type `MOVE` when the terminal prompts you.
2. Click the camera preview, hold your right palm still at a distance where depth is stable, and press **G**. On the first engagement the program enables motor torque.
3. Move your palm slowly by 2–3 cm. The arm should make a small corresponding movement. **S** pauses and **Q** exits. If palm depth is lost, the demo pauses until you press **G** again.
4. After exiting, support the arm before releasing motor torque. Run the command below and type `RELEASE` when prompted.

```bash
python linux_teleop.py release --arm-port "$ARM"
```

If a step fails, copy the full terminal error or capture a screenshot of the D455 preview or the Wizard scan.
