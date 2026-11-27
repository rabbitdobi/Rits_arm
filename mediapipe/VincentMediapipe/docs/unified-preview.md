# 五指、手腕和机械臂统一预览

这是模拟控制版本：只显示、记录目标，不打开电机串口，不发布 ROS 指令。

## 没有摄像头时

双击仓库根目录的 `查看离线控制演示.command`。它不需要摄像头或管理员密码，生成约 8 秒的合成输入演示，然后打开视频。合成演示包括开手、握拳校准、手腕中立位、手掌原点，以及三路动作变化。输出在 `mediapipe/VincentMediapipe/output/unified-offline-时间/`：

- `preview.mp4`：统一控制演示。
- `preview.png`：一帧预览。
- `targets.jsonl`：逐帧目标、有效性、失败原因和校准记录。
- `summary.json`：有效帧统计、模型配置和输入类型。

这能验证控制逻辑、计算和保存流程，不能验证真实深度精度或电机动作。

也可以从仓库根目录运行：

```bash
.venv/bin/python mediapipe/VincentMediapipe/unified_replay.py \
  --output mediapipe/VincentMediapipe/output/my-offline-demo
```

`--output` 必须是新的目录。要重放之前保存的原始 D455 采样，加上：

```bash
--samples mediapipe/VincentMediapipe/output/fingers-20261113-133103-863554.depth-samples
```

原始采样视频以每秒一张采样画面播放，保证保留每张画面；它不是原速录像。检测、控制计算和日志仍使用原始采集时间。原始采样重放重新检测 RGB 图像的 MediaPipe world landmarks，并使用同帧保存的深度测量。之前的采样没有五指和手腕校准记录，因此重放不会猜测校准值、自动生成这三路控制指令；它用于检查检测、缺失值处理和显示。合成演示单独验证校准后的动作。

普通录像也可以走完整程序：

```bash
.venv/bin/python mediapipe/VincentMediapipe/main.py \
  --video /absolute/path/to/video.mp4 --unified-preview --headless --record
```

普通 MP4 没有深度，机械臂通道保持无有效目标。无窗口运行时不能通过按键进行校准。

## D455 接回后

双击根目录 `开始统一控制预览.command`。Mac 可能因 USB 访问要求登录密码。在 D455 前约 50–80 cm 展示右手，保持两个小镜头无遮挡。

1. 手掌张开并稳定约一秒，按 **O**。
2. 握拳并稳定约一秒，按 **F**。
3. 手腕处于期望的中立姿势，按 **W**。
4. 手掌深度有效时按 **空格**，设定机械臂位移原点。
5. 缓慢移动和开合手指。**R** 清除所有校准，**Q/Esc** 保存退出。

五指校准使用至少十个连续有效样本，时间跨度至少 250 ms，稳定后取中位数；张开与握拳的特征必须有足够差异。姿势移动、检测丢失或跨度不足时拒绝校准，并显示原因。高帧率会保留更多样本满足时间要求。

## 三路输出的含义

| 通道 | 输入 | 输出 | 当前限制 |
|---|---|---|---|
| 五指 | MediaPipe 三维模型的指尖距离／掌长比例 | 拇、食、中、无名、小指顺序的五个 0–180 值；0 握拳、180 张开 | 开合代理量，不是解剖关节角；必须先 O/F 校准 |
| 手腕 | 相对中立手掌坐标系的扭转 | 弧度，以及 30–150 度的独立舵机预览 | 没有前臂姿态，不能称为真实腕关节角；硬件执行轴待定 |
| 机械臂 | D455 当前有效掌心 XYZ，单位米 | 相对原点的位置目标（米），四个关节角（弧度） | 未校准的四关节模拟几何；固定末端俯仰 |

五指字符串 `serial_preview` 只是现有 Arduino 五值格式的预览，不会实际发送。手腕不会作为第六项追加：目前的 Arduino 固件把手腕固定在 90 度。

默认位移映射：向相机靠近对应机械臂向前，相机 X 正向对应机械臂负 Y，相机 Y 正向对应机械臂向下；位移缩放 0.4。这个映射是操作约定，不是已标定的相机外参。

`teleop_model.json` 保存映射、工作空间、关节范围和速度。长度 130/124/126 mm 来自 [Gesture-Arm-Demo 的绘图参数](https://github.com/Gil-gil-glitch/Gesture-Arm-Demo/blob/main/src/gesture-arm-demo/gesture_arm_demo/pose_mimic.py)，范围参考其 [arm.yaml](https://github.com/Gil-gil-glitch/Gesture-Arm-Demo/blob/main/src/gesture-arm-demo/config/arm.yaml)。它们并未确认适用于我们组装后、装上五指手的机械臂。初始目标为肩部原点下的 `[0.25, 0, 0.13]` 米。

逆运动学检查工作空间、可达性和关节范围；有效动作限制为每个关节最多 1 rad/s。图中的橙色十字为请求位置，连杆为限速后的模拟位置。无有效目标时连杆变灰并显示 held，只是保留上一帧用于观察；日志中的当前目标关节值为 `null`。

手部丢失时五指和手腕输出为空；深度丢失时机械臂输出为空。超过一秒没有有效掌心深度，必须再次按空格设原点。它不代表真实机器人已经停车：本版本根本不控制硬件。

## 保存与后续实测

实时运行保留原有 CSV，并新增同名前缀的 `.targets.jsonl` 和 `.targets.config.json`；`--record` 保存带面板的视频。已有输出不覆盖。每帧含 `simulation_only: true`、`hardware_enabled: false` 和三路有效性。

摄像头接回后需实际检查：O/F 是否能稳定校准、五指端点是否正确、W 后扭转方向、空格后位移方向和深度连续性。接真实机械臂前，还需确认连杆／手部尺寸、零位、轴方向、限位及手腕执行轴，再设计硬件输出和失联处理。
