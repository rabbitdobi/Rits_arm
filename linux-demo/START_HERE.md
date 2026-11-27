# Linux 真机演示快速上手

先确认 **D455 能读到稳定的掌心深度**，再确认 **Dynamixel Wizard 能扫到四个电机**。两项通过后，再做机械臂示教和跟随。

## 1. 拉取演示代码

如果 Linux 上还没有这个仓库，在用来放项目的文件夹里打开终端：

```bash
git clone -b linux-teleop-demo https://github.com/rabbitdobi/Rits_arm.git Rits_arm_linux
cd Rits_arm_linux/linux-demo
```

如果已克隆并处于 `linux-teleop-demo` 分支，在现有仓库中运行 `git pull --ff-only`，然后进入 `linux-demo`。后面的命令均在该目录运行。

## 2. 插上 D455，打开预览

首次运行时新建虚拟环境并安装依赖：

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r mediapipe/VincentMediapipe/requirements.txt pyrealsense2 dynamixel-sdk
```

如果已装过依赖，每次打开新终端只需先运行 `source .venv/bin/activate`。

用 USB 3 数据线把 D455 直接插到 Linux，再运行：

```bash
python mediapipe/VincentMediapipe/main.py --realsense --no-trails
```

看到彩色画面和对齐深度画面后，把右手放在镜头前约 **65–90 cm**，确认掌心深度读数稳定。按 **Q** 退出。这一步只预览相机和追踪结果。

## 3. 用 Dynamixel Wizard 扫描机械臂

1. 确认 U2D2 已接到 Linux，四个电机已通过现有电源接线供电。
2. 打开 **Dynamixel Wizard**，扫描并记下 Linux 串口、波特率和电机 ID。演示预期 **Protocol 2.0、1 Mbps**，以及从底座到腕俯仰的 **001、002、003、004**。
3. 扫完关闭 Wizard，再让 Python 使用串口。若实际扫描结果与预期不同，先记录结果，核对配置后再继续。

如果需要确认 Linux 识别到了哪些设备，可以运行：

```bash
lsusb -t
ls -l /dev/serial/by-id/
```

## 4. 两项检查通过后

按 [完整手册的机械臂检查与示教步骤](README.md#3-只读检查并示教机械臂) 做只读检查，再记录中立位和六个小幅位移。首次测试只运行四轴跟随。Arduino 手腕和 ROS 2 可以在四轴跑通后再接。

如果中途出错，记下终端完整报错，或截取 D455 预览和 Wizard 的扫描结果。
