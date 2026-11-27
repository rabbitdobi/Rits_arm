"""Run a supervised A-to-B-to-A demo on the four XM430-W350 arm motors."""

import argparse
import sys
import time


JOINTS = {1: "base", 2: "shoulder", 3: "elbow", 4: "wrist pitch"}
MODEL_NUMBER = 1020
BAUDRATE = 1_000_000
DRIVE_MODE = 10
OPERATING_MODE = 11
MAX_POSITION = 48
MIN_POSITION = 52
TORQUE_ENABLE = 64
STATUS_RETURN_LEVEL = 68
HARDWARE_ERROR = 70
PROFILE_ACCELERATION = 108
PROFILE_VELOCITY = 112
GOAL_POSITION = 116
PRESENT_POSITION = 132

MAX_DEMO_TRAVEL = 114  # Encoder counts, approximately 10 degrees per axis.
START_TOLERANCE = 6
TRACKING_TOLERANCE = 24
INTERVAL = 0.1
SEGMENT_STEPS = 40


class DemoError(RuntimeError):
    pass


class ArmBus:
    def __init__(self, sdk, device):
        self.sdk = sdk
        self.port = sdk.PortHandler(device)
        self.packet = sdk.PacketHandler(2.0)
        if not self.port.openPort():
            raise DemoError(f"Cannot open {device}")
        try:
            if not self.port.setBaudRate(BAUDRATE):
                raise DemoError(f"Cannot set {device} to {BAUDRATE} bps")
        except BaseException:
            self.close()
            raise
        self.torque_may_be_on = False

    def close(self):
        self.port.closePort()

    def check(self, motor, operation, result, error):
        device = "Arm bus" if motor is None else f"ID {motor:03}"
        if result != self.sdk.COMM_SUCCESS:
            raise DemoError(f"{device}: {operation}: {self.packet.getTxRxResult(result)}")
        if error:
            raise DemoError(f"{device}: {operation}: {self.packet.getRxPacketError(error)}")

    def read(self, motor, address, size=1):
        reader = self.packet.read1ByteTxRx if size == 1 else self.packet.read4ByteTxRx
        value, result, error = reader(self.port, motor, address)
        self.check(motor, f"read address {address}", result, error)
        return value

    def write(self, motor, address, value, size=1):
        writer = self.packet.write1ByteTxRx if size == 1 else self.packet.write4ByteTxRx
        result, error = writer(self.port, motor, address, value)
        self.check(motor, f"write address {address}", result, error)

    def positions(self):
        readings = {}
        for motor in JOINTS:
            if self.read(motor, HARDWARE_ERROR):
                raise DemoError(f"ID {motor:03} reports a hardware error")
            readings[motor] = self.read(motor, PRESENT_POSITION, 4)
        return readings

    def inspect(self):
        limits = {}
        for motor, joint in JOINTS.items():
            model, result, error = self.packet.ping(self.port, motor)
            self.check(motor, "ping", result, error)
            if model != MODEL_NUMBER:
                raise DemoError(f"ID {motor:03}: expected XM430-W350, got model {model}")
            mode = self.read(motor, OPERATING_MODE)
            drive = self.read(motor, DRIVE_MODE)
            torque = self.read(motor, TORQUE_ENABLE)
            low = self.read(motor, MIN_POSITION, 4)
            high = self.read(motor, MAX_POSITION, 4)
            limits[motor] = (low, high)
            print(f"{motor:03} {joint}: mode={mode}, drive={drive}, torque={torque}, limits={low}..{high}",
                  flush=True)
            if mode != 3 or drive & 0x0C:
                raise DemoError(f"ID {motor:03}: needs Position Control, velocity-based profile and goal auto-torque off")
            if not 0 <= low < high <= 4095:
                raise DemoError(f"ID {motor:03}: unexpected single-turn limits {low}..{high}")
        return limits

    def capture(self, limits):
        if any(self.read(motor, TORQUE_ENABLE) for motor in JOINTS):
            raise DemoError("Torque must be off on all four motors during teaching")
        pose = self.positions()
        time.sleep(INTERVAL)
        require_near(pose, self.positions(), START_TOLERANCE, "Hold the arm still while capturing")
        for motor, value in pose.items():
            low, high = limits[motor]
            if not low <= value <= high:
                raise DemoError(f"ID {motor:03}: {value} is outside {low}..{high}; no wraparound is used")
        return pose

    def enable(self, start, limits):
        current = self.capture(limits)
        require_near(start, current, START_TOLERANCE, "Return to pose A before enabling torque")
        for motor in JOINTS:
            if self.read(motor, STATUS_RETURN_LEVEL) != 2:
                raise DemoError(f"ID {motor:03}: status return level must acknowledge writes")
        for motor, value in current.items():
            self.write(motor, PROFILE_VELOCITY, 6, 4)
            self.write(motor, PROFILE_ACCELERATION, 1, 4)
            self.write(motor, GOAL_POSITION, value, 4)
        require_near(current, self.positions(), START_TOLERANCE, "Arm moved before torque enable")
        self.torque_may_be_on = True
        for motor in JOINTS:
            self.write(motor, TORQUE_ENABLE, 1)
        require_near(current, self.positions(), START_TOLERANCE, "Arm moved when torque was enabled")
        for motor, value in current.items():
            if self.read(motor, GOAL_POSITION, 4) != value:
                raise DemoError(f"ID {motor:03}: starting goal changed during enable")
        return current

    def send_pose(self, pose):
        writer = self.sdk.GroupSyncWrite(self.port, self.packet, GOAL_POSITION, 4)
        for motor, value in pose.items():
            if not writer.addParam(motor, list(value.to_bytes(4, "little"))):
                raise DemoError(f"Could not queue position for ID {motor:03}")
        self.check(None, "send positions", writer.txPacket(), 0)

    def release(self):
        errors = []
        for motor in JOINTS:
            try:
                self.write(motor, TORQUE_ENABLE, 0)
            except DemoError as error:
                errors.append(str(error))
        if errors:
            raise DemoError("; ".join(errors))
        self.torque_may_be_on = False


def require_near(expected, actual, tolerance, context):
    for motor, position in expected.items():
        if abs(actual[motor] - position) > tolerance:
            raise DemoError(f"{context}: ID {motor:03}, expected {position}, read {actual[motor]}")


def sweep(bus, start, end):
    previous = start
    for step in range(1, SEGMENT_STEPS + 1):
        require_near(previous, bus.positions(), TRACKING_TOLERANCE, "Position tracking failed")
        phase = step / SEGMENT_STEPS
        fraction = phase * phase * (3 - 2 * phase)
        goal = {motor: round(value + fraction * (end[motor] - value)) for motor, value in start.items()}
        if goal != previous:
            bus.send_pose(goal)
            previous = goal
        time.sleep(INTERVAL)
    for _ in range(20):
        actual = bus.positions()
        if all(abs(actual[motor] - end[motor]) <= START_TOLERANCE for motor in JOINTS):
            return
        time.sleep(INTERVAL)
    raise DemoError(f"Arm did not settle at the endpoint. Last read: {actual}")


def run_demo(bus, limits):
    input("With torque off, support the arm in pose A. Press Enter to capture: ")
    start = bus.capture(limits)
    print(f"A: {start}")
    input("Teach nearby pose B along a clear path (up to 10 degrees per axis). Press Enter: ")
    end = bus.capture(limits)
    print(f"B: {end}")
    travel = max(abs(end[motor] - start[motor]) for motor in JOINTS)
    if not START_TOLERANCE < travel <= MAX_DEMO_TRAVEL:
        raise DemoError(f"Teach a distinct, nearby B (largest joint change: {travel} counts)")
    confirmation = input("Return to A and keep the path clear. Type MOVE to replay A -> B -> A: ")
    if confirmation != "MOVE":
        print("Cancelled.")
        return
    current = bus.enable(start, limits)
    require_near(end, current, MAX_DEMO_TRAVEL + START_TOLERANCE, "Starting pose is too far from B")
    sweep(bus, current, end)
    sweep(bus, end, start)
    input("Demo finished at A. Support the arm, then press Enter to release torque: ")
    bus.release()
    print("Torque released.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", default="/dev/ttyUSB0", help="Serial adapter device")
    parser.add_argument("--move", action="store_true", help="Teach and replay two positions; default is read-only")
    args = parser.parse_args()
    try:
        import dynamixel_sdk
    except ImportError:
        parser.exit(1, "Install the ROBOTIS Python SDK: python3 -m pip install dynamixel-sdk\n")

    bus = None
    try:
        bus = ArmBus(dynamixel_sdk, args.port)
        limits = bus.inspect()
        print(f"Present positions: {bus.positions()}", flush=True)
        if args.move:
            run_demo(bus, limits)
    except (DemoError, OSError, EOFError, KeyboardInterrupt) as error:
        print(f"Stopped: {error or 'operator interrupted'}", file=sys.stderr)
        return 1
    finally:
        if bus is not None:
            if bus.torque_may_be_on:
                print("Torque may still be on. Support the arm before disabling torque in Wizard.", file=sys.stderr)
            bus.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
