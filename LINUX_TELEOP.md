# Linux 上的 D455 机械臂遥操作

以下命令以 Ubuntu 24.04 x86-64 桌面版、Python 3.12 和有图形桌面的本机为例。在解压后的目录运行。摄像头先单独跑通，然后测试 XM430，最后接 Arduino 五指。整个演示用 Python 直接控制两个串口，无需 ROS。

## 1. 安装并接线

```bash
sudo apt update
sudo apt install -y python3-venv curl usbutils v4l-utils libgl1 libglib2.0-0t64 libxcb-cursor0 libxkbcommon-x11-0
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r mediapipe/VincentMediapipe/requirements.txt pyrealsense2 dynamixel-sdk pyserial
python -c 'import cv2, mediapipe, pyrealsense2, dynamixel_sdk, serial; print("Imports OK")'

curl -fL https://raw.githubusercontent.com/realsenseai/librealsense/master/config/99-realsense-libusb.rules -o /tmp/99-realsense-libusb.rules
sudo install -m 644 /tmp/99-realsense-libusb.rules /etc/udev/rules.d/99-realsense-libusb.rules
sudo udevadm control --reload-rules
sudo udevadm trigger
sudo usermod -aG dialout "$USER"
```

注销再登录让 `dialout` 生效，回到项目目录重新 `. .venv/bin/activate`，然后拔插设备。用普通用户运行演示。

| 设备 | 接法 |
|---|---|
| RealSense D455 | 用 USB 3 数据线直接插 Linux 主机。固定摄像头，镜头对准操作者右手。 |
| 四个 XM430-W350-T | 主机 USB → U2D2 → 3 针 TTL 总线。四个舵机沿总线串接，通过 Power Hub 或已有的电机电源接线供电。U2D2 负责数据，电机用独立电源。断电时接插电机线。 |
| Arduino / uHand UNO | 主机另一 USB 口 → Arduino。保持团队原有舵机接线和供电。若板上已有接收固件，直接使用。若需要刷写，ZIP 内带有团队的 `arduino/arduinohand/arduinohand.ino`。打开串口可能重启 Uno，重启时五指会移动到张开位置。 |

```bash
lsusb -t
ls -l /dev/serial/by-id/
```

先只插 U2D2，记下它出现的路径。再插 Arduino，记下新增路径。把下面右边的示例名替换成实际路径。若系统只有 `/dev/ttyUSB0` 或 `/dev/ttyACM0`，用逐个接入的方式确认哪个属于哪块板。

```bash
ARM=/dev/serial/by-id/替换成U2D2路径
HAND=/dev/serial/by-id/替换成Arduino路径
```

## 2. 先验证摄像头

```bash
python mediapipe/VincentMediapipe/realsense_probe.py --preview
python mediapipe/VincentMediapipe/main.py --realsense --no-trails
```

第一条应显示 RGB 与对齐深度。第二条用来核对右手、掌心深度和跟踪稳定性，按 **Q** 退出后再运行下一条。初次把右手放在 D455 前约 **65–90 cm**，掌心进入画面中央。演示只接受 0.55–1.2 m 范围内的有效掌心 XYZ。窗口左右镜像，计算使用未镜像的相机坐标。若 D455 打不开，核对 `lsusb -t` 中是否走 SuperSpeed（通常显示 `5000M`）、是否已有其他应用占用以及 udev 规则是否生效。若 Wayland 下 Qt 无法建窗口，在有 XWayland 的桌面会话里试 `QT_QPA_PLATFORM=xcb`。

## 3. 只读检查并示教机械臂

关闭 Dynamixel Wizard 和其他串口程序。固定底座，清空臂周围，准备能随时操作的电机电源开关。断扭矩时支撑手臂，示教时保持末端俯仰尽量一致。以实际装上的手掌或工具上的固定标记为测量点，全程用同一个点。

```bash
python xm430_arm_demo.py --port "$ARM"
python linux_teleop.py teach --arm-port "$ARM" --calibration bench.json
```

第一条只读核对 XM430 ID **001 底座、002 肩、003 肘、004 腕俯仰**（从下到上）、Protocol 2.0、1 Mbps、位置模式、编码器限位及状态。如果 ID、波特率、运行模式与现场设置不同，检查电机配置后再继续。先确认 `torque=0`。

第二条依次记录中立位、沿相机 X/Y/Z 各移动正负 **20 mm** 的六个位姿。用直尺或标记测量，沿单轴移动时尽量保持另两轴与中立点重合。从摄像头后方往前看，X 正向朝右，Y 正向朝下，Z 正向远离摄像头。每个端点都以同一个中立点为基准。选一个关节有余量、工具路径清空、无自碰的中立姿势，覆盖六个方向。示教结束后回到中立位。每个端点每轴最多相对中立变化 114 encoder counts（约 10°），程序会拒绝越限或三个方向混在一起的标定。移动相机、底座或更换末端后重新示教，用新文件名。

适合先做空载测试。首次验证只让操作者的手缓慢移动 2–3 cm，核对六个方向以及遮住掌心时能否暂停。局部关节插值不提供避碰或负载补偿，也不保证整段轨迹的末端始终精确沿直线。

## 4. 运行三种模式

```bash
# 先试机械臂四轴
python linux_teleop.py run --arm-port "$ARM" --calibration bench.json

# 然后单独试 Arduino 五指
python linux_teleop.py run --hand-port "$HAND"

# 最后同时运行
python linux_teleop.py run --arm-port "$ARM" --calibration bench.json --hand-port "$HAND"
```

1. 在终端确认路径清空并输入 `MOVE`。用了 Arduino 时，观察它初始化后五指确实张开，再输入 `OPEN`。
2. 点一下预览窗口让它得到键盘焦点。用了 Arduino 时，把右手张开稳定约一秒后按 **O**，再握拳稳定约一秒后按 **F**。窗口侧栏显示是否通过校准。
3. 机械臂处于示教的中立位，右手掌心有稳定深度时按 **G**。第一次按 **G** 会开启机械臂扭矩；之后按 **G** 会从暂停时的末端目标重新对齐操作者当前掌心位置。
4. 缓慢平移掌心并开合手指。**S** 暂停。掌心深度失效、跳变、处理间隔过长或所选通道的追踪丢失会停止发送新目标，恢复后需要手动按 **G**。**Q/Esc** 退出，退出后舵机可能继续保持最后目标。
5. 退出后，先用支架或人手支撑机械臂，再执行下面命令并输入 `RELEASE` 解除四轴扭矩。Arduino 会保持最后接收的姿势；需要断电时按现场手部供电方式处理。若出现卡碰或异常运动，立即操作实体电源开关，同时防止失去扭矩后机械臂下坠。

```bash
python linux_teleop.py release --arm-port "$ARM"
```

| 通道 | 映射 |
|---|---|
| 机械臂 | D455 同帧 RGB＋实测深度 → MediaPipe 掌心 XYZ → 相对位移缩放至 25% → 在七个示教位姿间插值 → XM430 四轴。演示位移限制在三个轴绝对位移合计 20 mm 内。每 100 ms 至多发送一个新目标，每轴单步最多 3 counts。 |
| 五指 | MediaPipe 三维手关键点 → O/F 标定 → 拇、食、中、无名、小指五个 0–180 值 → USB 串口 115200、逗号分隔、换行结尾 → Shota 的 Arduino 固件。Arduino 对拇指方向和舵机角度做转换。 |
| 腕 | XM430 **004** 是机械臂的腕俯仰，可参与示教插值。Arduino 上独立的手腕舵机保持 90°，现有固件接收五个值。 |

参考：[RealSense Linux 安装](https://github.com/realsenseai/librealsense/blob/master/doc/installation.md) · [ROBOTIS U2D2 接线](https://emanual.robotis.com/docs/en/software/dynamixel/dynamixel_sdk/device_setup/) · [XM430-W350 控制表](https://emanual.robotis.com/docs/en/dxl/x/xm430-w350/)
