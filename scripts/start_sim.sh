#!/bin/bash
# ================================================================
# XTDrone 两机仿真一键启动脚本
#
# 用法：
#   ./start_sim.sh              # 启动仿真（前台运行，Ctrl+C 退出）
#   ./start_sim.sh --headless   # 无 GUI 模式
# ================================================================
set -e
source /opt/ros/noetic/setup.bash
source ~/catkin_ws/devel/setup.bash
source ~/PX4_Firmware/Tools/setup_gazebo.bash ~/PX4_Firmware ~/PX4_Firmware/build/px4_sitl_default
export ROS_PACKAGE_PATH=$ROS_PACKAGE_PATH:~/PX4_Firmware:~/PX4_Firmware/Tools/sitl_gazebo

GUI="true"
if [ "$1" = "--headless" ]; then
    GUI="false"
    echo "[start_sim] 无 GUI 模式"
fi

if ! grep -q "COM_RCL_EXCEPT" ~/PX4_Firmware/build/px4_sitl_default/etc/init.d-posix/rcS 2>/dev/null; then
    echo "[start_sim] 写入 COM_RCL_EXCEPT 参数..."
    echo "param set COM_RCL_EXCEPT 4" >> ~/PX4_Firmware/build/px4_sitl_default/etc/init.d-posix/rcS
fi
if ! grep -q "COM_RCL_EXCEPT" ~/PX4_Firmware/ROMFS/px4fmu_common/init.d-posix/rcS 2>/dev/null; then
    echo "param set COM_RCL_EXCEPT 4" >> ~/PX4_Firmware/ROMFS/px4fmu_common/init.d-posix/rcS
fi

echo "============================================"
echo "  两机仿真启动中..."
echo "  等 Gazebo 就绪后，在另一个终端运行："
echo "    ./run_dual_takeoff.sh  或  ./run_formation.sh"
echo "============================================"
roslaunch px4 multi_iris_2.launch gui:=$GUI
