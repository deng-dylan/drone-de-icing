# 环境搭建指南（从零开始）

本文档帮助在全新的 Windows + WSL2 环境上搭建完整的多机仿真环境。

---

## 前置条件

请确保你的 Windows 系统已启用 WSL2，并安装了 Ubuntu 20.04。如果还没有，请在 PowerShell（管理员）中执行：

```powershell
wsl --install -d Ubuntu-20.04
```

重启后设置用户名和密码，然后继续以下步骤。所有命令都在 **WSL2 Ubuntu 终端**中执行。

---

##强烈推荐
https://www.yuque.com/xtdrone/manual_cn/install_scripts#
在这个网址有一键安装脚本，使用方式见网址内部
## 第一步：安装 ROS Noetic

```bash
# 添加 ROS 软件源
sudo sh -c 'echo "deb http://packages.ros.org/ros/ubuntu focal main" > /etc/apt/sources.list.d/ros-latest.list'
curl -s https://raw.githubusercontent.com/ros/rosdistro/master/ros.asc | sudo apt-key add -

# 安装 ROS Noetic 完整版
sudo apt update
sudo apt install -y ros-noetic-desktop-full

# 初始化 rosdep
sudo rosdep init
rosdep update

# 写入 .bashrc
echo "source /opt/ros/noetic/setup.bash" >> ~/.bashrc
source ~/.bashrc
```

---

## 第二步：安装 MAVROS

```bash
sudo apt install -y ros-noetic-mavros ros-noetic-mavros-extras

# 安装 GeographicLib 数据集（MAVROS 依赖）
wget https://raw.githubusercontent.com/mavlink/mavros/master/mavros/scripts/install_geographiclib_datasets.sh
chmod +x install_geographiclib_datasets.sh
sudo ./install_geographiclib_datasets.sh
rm install_geographiclib_datasets.sh
```

---

## 第三步：安装 PX4 v1.13.2

```bash
# 安装编译依赖
sudo apt install -y git python3-pip cmake build-essential genromfs ninja-build \
    libgstreamer1.0-dev libgstreamer-plugins-base1.0-dev gstreamer1.0-plugins-bad \
    gstreamer1.0-plugins-base gstreamer1.0-plugins-good gstreamer1.0-plugins-ugly \
    xmlstarlet

# 克隆 PX4（使用 XTDrone 适配的 v1.13.2 分支）
cd ~
git clone https://github.com/PX4/PX4-Autopilot.git PX4_Firmware --recursive
cd PX4_Firmware
git checkout v1.13.2

# 安装 PX4 依赖
bash Tools/setup/ubuntu.sh --no-nuttx

# 编译 SITL
DONT_RUN=1 make px4_sitl_default gazebo
```

编译过程可能需要 10-30 分钟，取决于机器性能。编译成功后终端会显示 `Build files have been written to: ...`。

---

## 第四步：安装 XTDrone

```bash
cd ~
git clone https://gitee.com/robin_shaun/XTDrone.git

# 复制 XTDrone 的配置文件到 PX4
cp -r ~/XTDrone/sitl_config/init.d-posix/* ~/PX4_Firmware/ROMFS/px4fmu_common/init.d-posix/
cp -r ~/XTDrone/sitl_config/launch/* ~/PX4_Firmware/launch/

# 复制 Gazebo 模型
cp -r ~/XTDrone/sitl_config/models/* ~/.gazebo/models/ 2>/dev/null
mkdir -p ~/.gazebo/models
cp -r ~/XTDrone/sitl_config/models/* ~/.gazebo/models/

# 重新编译 PX4（让新配置生效）
cd ~/PX4_Firmware
DONT_RUN=1 make px4_sitl_default gazebo
```

---

## 第五步：创建 catkin 工作空间

```bash
mkdir -p ~/catkin_ws/src
cd ~/catkin_ws
catkin init  # 或 catkin_make
catkin build  # 或 catkin_make

# 写入 .bashrc
echo "source ~/catkin_ws/devel/setup.bash" >> ~/.bashrc
source ~/.bashrc
```

---

## 第六步：部署本项目

```bash
# 克隆项目到 catkin 工作空间
cd ~/catkin_ws/src
git clone git@github.com:deng-dylan/drone-de-icing.git multi_uav

# 复制 launch 文件到 PX4 目录
cp ~/catkin_ws/src/multi_uav/launch/*.launch ~/PX4_Firmware/launch/

# 设置 COM_RCL_EXCEPT 参数（OFFBOARD 模式的 RC 丢失豁免，SITL 必需）
echo "param set COM_RCL_EXCEPT 4" >> ~/PX4_Firmware/build/px4_sitl_default/etc/init.d-posix/rcS
echo "param set COM_RCL_EXCEPT 4" >> ~/PX4_Firmware/ROMFS/px4fmu_common/init.d-posix/rcS

# 安装 Python 依赖
pip3 install pyquaternion
```

---

## 第七步：验证安装

```bash
# 启动两机仿真
cd ~/catkin_ws/src/multi_uav/scripts
./start_sim.sh

# （在另一个终端）运行两机独立控制测试
cd ~/catkin_ws/src/multi_uav/scripts
./run_dual_takeoff.sh
```

如果你能在 Gazebo 窗口中看到两架 iris 分别飞到不同高度然后降落，说明环境搭建成功。

---

## 常见问题

### Q: Gazebo 窗口打不开 / 黑屏

WSL2 需要图形显示支持。Windows 11 自带 WSLg，通常自动工作。如果不行，尝试：

```bash
# 确认 DISPLAY 变量
echo $DISPLAY
# 应该输出类似 :0 或 :0.0

# 如果为空，手动设置
export DISPLAY=:0
```

### Q: PX4 解锁失败（Arming denied）

大概率是 `COM_RCL_EXCEPT` 参数没有生效。检查：

```bash
grep "COM_RCL_EXCEPT" ~/PX4_Firmware/build/px4_sitl_default/etc/init.d-posix/rcS
```

如果没有输出，手动添加：

```bash
echo "param set COM_RCL_EXCEPT 4" >> ~/PX4_Firmware/build/px4_sitl_default/etc/init.d-posix/rcS
```

### Q: 五机仿真很卡

5 个 PX4 SITL 实例 + Gazebo 对系统资源要求较高。建议至少 16GB 内存。如果实在太卡，可以先用两机版本验证。

### Q: catkin build 报错

确保 .bashrc 中只 source 了 ROS Noetic，没有同时 source ROS2：

```bash
grep "source.*ros" ~/.bashrc
# 应该只有 /opt/ros/noetic/setup.bash
```

---

## 关键路径速查

| 用途 | 路径 |
|------|------|
| PX4 固件 | `~/PX4_Firmware` |
| XTDrone 源码 | `~/XTDrone` |
| catkin 工作空间 | `~/catkin_ws` |
| 本项目 | `~/catkin_ws/src/multi_uav` |
| Gazebo 模型 | `~/.gazebo/models` |
| ROS Noetic | `/opt/ros/noetic` |
| MAVROS | `/opt/ros/noetic/share/mavros` |
