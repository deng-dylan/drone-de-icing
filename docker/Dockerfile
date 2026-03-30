###############################################################################
# drone-de-icing Dockerfile
#
# 构建一个包含 ROS Noetic + PX4 v1.13.2 + Gazebo 11 + MAVROS + XTDrone 的
# 完整多机仿真环境，开箱即用。
#
# 构建：docker build -t drone-de-icing .
# 运行：docker run -it --rm -e DISPLAY=$DISPLAY \
#          -v /tmp/.X11-unix:/tmp/.X11-unix drone-de-icing bash
###############################################################################

FROM ros:noetic-ros-base-focal

ENV DEBIAN_FRONTEND=noninteractive
ENV PX4_HOME=/root/PX4_Firmware
ENV CATKIN_WS=/root/catkin_ws

SHELL ["/bin/bash", "-c"]

# =============================================================================
# 第一层：系统依赖 + ROS 包 + Gazebo 11
# =============================================================================
RUN apt-get update && apt-get install -y --no-install-recommends \
    # 基本工具
    git wget curl lsb-release gnupg2 sudo vim \
    python3-pip python3-setuptools python3-wheel \
    cmake build-essential ninja-build genromfs xmlstarlet \
    bc \
    # ROS 工具
    python3-catkin-tools python3-rosinstall python3-rosinstall-generator \
    python3-wstool python3-rosdep \
    # ROS Noetic 桌面版（含 Gazebo 11）
    ros-noetic-desktop-full \
    # MAVROS
    ros-noetic-mavros ros-noetic-mavros-extras \
    # Gazebo 开发库
    ros-noetic-gazebo-ros ros-noetic-gazebo-plugins \
    # GStreamer（PX4 依赖）
    libgstreamer1.0-dev libgstreamer-plugins-base1.0-dev \
    gstreamer1.0-plugins-bad gstreamer1.0-plugins-base \
    gstreamer1.0-plugins-good gstreamer1.0-plugins-ugly \
    # X11 显示支持
    x11-apps mesa-utils libgl1-mesa-dri libgl1-mesa-glx \
    && rm -rf /var/lib/apt/lists/*

# 安装 GeographicLib 数据集（MAVROS 需要）
RUN wget -q https://raw.githubusercontent.com/mavlink/mavros/master/mavros/scripts/install_geographiclib_datasets.sh \
    && chmod +x install_geographiclib_datasets.sh \
    && ./install_geographiclib_datasets.sh \
    && rm install_geographiclib_datasets.sh

# Python 依赖
RUN pip3 install pyquaternion

# =============================================================================
# 第二层：PX4 v1.13.2
# =============================================================================
RUN git clone --depth 1 --branch v1.13.2 --recursive \
    https://github.com/PX4/PX4-Autopilot.git ${PX4_HOME}

WORKDIR ${PX4_HOME}

# 安装 PX4 特有依赖（跳过 nuttx 交叉编译工具链，SITL 不需要）
RUN bash Tools/setup/ubuntu.sh --no-nuttx --no-sim-tools 2>/dev/null; exit 0

# 编译 SITL
RUN source /opt/ros/noetic/setup.bash \
    && DONT_RUN=1 make px4_sitl_default gazebo

# =============================================================================
# 第三层：XTDrone
# =============================================================================
RUN cd /root && git clone --depth 1 https://gitee.com/robin_shaun/XTDrone.git

# 复制 XTDrone 配置到 PX4
RUN cp -r /root/XTDrone/sitl_config/init.d-posix/* ${PX4_HOME}/ROMFS/px4fmu_common/init.d-posix/ \
    && cp -r /root/XTDrone/sitl_config/launch/* ${PX4_HOME}/launch/

# 复制 Gazebo 模型
RUN mkdir -p /root/.gazebo/models \
    && cp -r /root/XTDrone/sitl_config/models/* /root/.gazebo/models/ 2>/dev/null; exit 0

# 重新编译以加载新配置
RUN source /opt/ros/noetic/setup.bash \
    && cd ${PX4_HOME} \
    && DONT_RUN=1 make px4_sitl_default gazebo

# =============================================================================
# 第四层：catkin 工作空间 + 项目代码
# =============================================================================
RUN mkdir -p ${CATKIN_WS}/src
WORKDIR ${CATKIN_WS}
RUN source /opt/ros/noetic/setup.bash && catkin init && catkin build

# 复制项目文件
COPY launch/ ${CATKIN_WS}/src/multi_uav/launch/
COPY scripts/ ${CATKIN_WS}/src/multi_uav/scripts/
COPY docs/ ${CATKIN_WS}/src/multi_uav/docs/
COPY README.md ${CATKIN_WS}/src/multi_uav/

# 复制 launch 文件到 PX4 目录
RUN cp ${CATKIN_WS}/src/multi_uav/launch/*.launch ${PX4_HOME}/launch/

# 设置脚本可执行权限
RUN chmod +x ${CATKIN_WS}/src/multi_uav/scripts/*.sh \
    && chmod +x ${CATKIN_WS}/src/multi_uav/scripts/*.py

# =============================================================================
# 第五层：环境配置
# =============================================================================

# 写入 COM_RCL_EXCEPT（OFFBOARD 模式 RC 丢失豁免，SITL 必需）
RUN echo "param set COM_RCL_EXCEPT 4" >> ${PX4_HOME}/build/px4_sitl_default/etc/init.d-posix/rcS \
    && echo "param set COM_RCL_EXCEPT 4" >> ${PX4_HOME}/ROMFS/px4fmu_common/init.d-posix/rcS

# 配置 .bashrc
RUN echo "" >> /root/.bashrc \
    && echo "# === drone-de-icing 环境 ===" >> /root/.bashrc \
    && echo "source /opt/ros/noetic/setup.bash" >> /root/.bashrc \
    && echo "source ${CATKIN_WS}/devel/setup.bash" >> /root/.bashrc \
    && echo "source ${PX4_HOME}/Tools/setup_gazebo.bash ${PX4_HOME} ${PX4_HOME}/build/px4_sitl_default" >> /root/.bashrc \
    && echo "export ROS_PACKAGE_PATH=\$ROS_PACKAGE_PATH:${PX4_HOME}:${PX4_HOME}/Tools/sitl_gazebo" >> /root/.bashrc

WORKDIR ${CATKIN_WS}/src/multi_uav

CMD ["bash"]
