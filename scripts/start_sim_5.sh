#!/bin/bash
# 五机仿真一键启动
set -e
source /opt/ros/noetic/setup.bash
source ~/catkin_ws/devel/setup.bash
source ~/PX4_Firmware/Tools/setup_gazebo.bash ~/PX4_Firmware ~/PX4_Firmware/build/px4_sitl_default
export ROS_PACKAGE_PATH=$ROS_PACKAGE_PATH:~/PX4_Firmware:~/PX4_Firmware/Tools/sitl_gazebo

if ! grep -q "COM_RCL_EXCEPT" ~/PX4_Firmware/build/px4_sitl_default/etc/init.d-posix/rcS 2>/dev/null; then
    echo "param set COM_RCL_EXCEPT 4" >> ~/PX4_Firmware/build/px4_sitl_default/etc/init.d-posix/rcS
fi

echo "============================================"
echo "  五机仿真启动中（五环阵型）..."
echo "  注意：5 架飞机启动较慢，请耐心等待"
echo "  等 Gazebo 中 5 架飞机全部出现后，在另一终端运行："
echo "    ./run_five_ring_show.sh"
echo "============================================"
roslaunch px4 multi_iris_5.launch
