# drone-de-icing —— 多无人机编队仿真系统

基于 **XTDrone + PX4 v1.13.2 + Gazebo 11 + MAVROS** 的多无人机编队仿真项目。  
支持 2~5 架 iris 无人机的独立控制、同步起飞/降落、固定偏移编队跟随和空中编队表演。

---

## 快速开始

### 方式一：Docker（推荐）

无需配置环境，一行命令启动。详见 [Docker 使用说明](docs/DOCKER.md)。

```bash
cd docker
docker build -t drone-de-icing .
# Linux / WSL2（需要 X11 显示支持）
xhost +local:docker
docker run -it --rm \
  -e DISPLAY=$DISPLAY \
  -v /tmp/.X11-unix:/tmp/.X11-unix \
  drone-de-icing
```

### 方式二：本地环境（适合已有 XTDrone 环境）

如果你已经有 WSL2 + Ubuntu 20.04 + ROS Noetic + PX4 1.13 的环境，可以直接使用。  
详细环境搭建步骤见 [环境搭建指南](docs/SETUP.md)。

```bash
# 1. 克隆仓库
cd ~/catkin_ws/src
git clone git@github.com:deng-dylan/drone-de-icing.git multi_uav

# 2. 复制 launch 文件到 PX4 目录
cp multi_uav/launch/*.launch ~/PX4_Firmware/launch/

# 3. 确保 COM_RCL_EXCEPT 参数已写入（SITL 必须）
# 脚本会自动检测并写入，也可以手动确认：
grep -q "COM_RCL_EXCEPT" ~/PX4_Firmware/build/px4_sitl_default/etc/init.d-posix/rcS || \
  echo "param set COM_RCL_EXCEPT 4" >> ~/PX4_Firmware/build/px4_sitl_default/etc/init.d-posix/rcS

# 4. 启动仿真（终端 A）
cd multi_uav/scripts
./start_sim_5.sh

# 5. 运行表演（终端 B，等 Gazebo 中 5 架飞机出现后）
./run_five_ring_show.sh
```

---

## 可用的演示脚本

| 脚本 | 功能 | 飞机数量 |
|------|------|---------|
| `start_sim.sh` + `run_dual_takeoff.sh` | 两机独立控制：分别飞到不同位置 | 2 |
| `start_sim.sh` + `run_formation.sh` | 两机编队跟随：从机保持固定偏移跟随主机 | 2 |
| `start_sim_5.sh` + `run_five_ring_show.sh` | 五环表演：逐架起飞→排成一行→画正方形→回家→逐架降落 | 5 |

---

## 项目结构

```
drone-de-icing/
├── README.md                          # 本文件
├── launch/
│   ├── multi_iris_2.launch            # 两机仿真 launch 文件
│   └── multi_iris_5.launch            # 五机仿真 launch 文件（五环阵型）
├── scripts/
│   ├── start_sim.sh                   # 一键启动两机仿真
│   ├── start_sim_5.sh                 # 一键启动五机仿真
│   ├── run_dual_takeoff.sh            # 运行两机独立控制
│   ├── run_formation.sh               # 运行两机编队跟随
│   ├── run_five_ring_show.sh          # 运行五环表演
│   ├── single_takeoff_test.py         # 单机起飞测试（调试用）
│   ├── dual_takeoff_test.py           # 两机独立控制脚本
│   ├── formation_follow_test.py       # 两机编队跟随脚本
│   └── five_ring_show.py              # 五环表演编排脚本
├── docs/
│   ├── SETUP.md                       # 环境搭建指南（从零开始）
│   ├── DOCKER.md                      # Docker 使用说明
│   └── 环境清单.md                     # 开发环境配置快照
└── docker/
    └── Dockerfile                     # Docker 构建文件
```

---

## 代码架构

### UAVController 类

项目的核心是 `UAVController` 类，每架无人机被抽象为一个独立的控制对象：

```python
uav0 = UAVController('iris_0', spawn_x=0.0, spawn_y=0.0)
uav1 = UAVController('iris_1', spawn_x=3.0, spawn_y=0.0)

uav0.set_target_world(4.0, 0.0, 2.0)  # 用世界坐标设置目标（自动换算本地坐标）
uav0.publish_target()                   # 发布目标点到 MAVROS
uav0.arm()                              # 解锁电机
```

通过 namespace 参数区分不同飞机，同一份代码可控制任意数量的飞机。扩展到更多飞机只需修改 launch 文件（添加新的 group）和控制脚本（添加新的 UAVController 实例）。

### 坐标系说明

每架飞机的 `local_position` 是相对于自身 EKF 原点的坐标，不同飞机的原点不在同一位置。`UAVController` 封装了坐标换算逻辑：

```
world_position = local_position + spawn_position
local_target   = world_target   - spawn_position
```

使用 `set_target_world()` 可以直接用 Gazebo 世界坐标设置目标，内部自动完成换算。

---

## 关键参数说明

| 参数 | 值 | 说明 |
|------|-----|------|
| `COM_RCL_EXCEPT` | 4 | 豁免 OFFBOARD 模式的 RC 丢失检查（SITL 必需） |
| `COM_RC_IN_MODE` | 1 | 不要求 RC 校准（XTDrone rcS 已设置） |
| setpoint 预喂时间 | ≥2 秒（代码中用 5 秒） | PX4 要求切 OFFBOARD 前持续收到 setpoint |
| setpoint 频率 | ≥2Hz（代码中用 20Hz） | 低于此频率 PX4 会触发 OFFBOARD 失控保护 |

---

## 后续扩展方向

本项目为基础框架，后续可扩展：

- **三机/多机**：在 launch 文件中按模板添加更多 group，控制脚本中添加更多 UAVController 实例
- **任务分配**：在 UAVController 之上添加任务管理层，支持动态航点分配
- **视觉协同**：集成 XTDrone 的 sensing 模块，实现基于视觉的编队
- **路径规划**：集成 XTDrone 的 motion_planning 模块
- **通信桥接**：使用 XTDrone 的 `multirotor_communication.py` 实现键盘控制

---

## 环境要求（本地部署）

| 组件 | 版本 |
|------|------|
| OS | WSL2 + Ubuntu 20.04 |
| ROS | Noetic |
| PX4 | v1.13.2（分支 `xtdrone/dev`） |
| Gazebo | 11 |
| MAVROS | apt 安装版 |
| XTDrone | 适配 PX4 1.13 版 |
| Python | 3.8+ |
