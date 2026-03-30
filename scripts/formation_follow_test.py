#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
简单编队测试脚本：固定偏移跟随

架构：
  - iris_0 为主机（leader），沿预设航线自主飞行
  - iris_1 为从机（follower），实时读取主机位置，保持固定偏移跟随

编队逻辑：
  从机目标位置 = 主机当前位置 + 编队偏移量（在主机坐标系下）
  由于两架飞机的 local_position 各自基于自身 EKF 原点，
  需要用 spawn 位置差来做坐标系换算。

坐标系换算说明：
  设 iris_0 的 spawn 位置为 G0 = (0, 0, 0)（Gazebo 世界坐标）
     iris_1 的 spawn 位置为 G1 = (3, 0, 0)
  spawn_offset = G1 - G0 = (3, 0, 0)

  当 iris_0 报告自身位置为 P0_local（在 iris_0 坐标系下），
  iris_0 在 Gazebo 世界坐标中的真实位置为：P0_world = G0 + P0_local = P0_local

  我们希望 iris_1 在 Gazebo 世界坐标中飞到：
    P1_world_desired = P0_world + formation_offset
                     = P0_local + formation_offset

  但 iris_1 的 setpoint 是在 iris_1 自己的坐标系下发送的，所以：
    P1_local_target = P1_world_desired - G1
                    = P0_local + formation_offset - spawn_offset
"""

import rospy
from geometry_msgs.msg import PoseStamped
from mavros_msgs.msg import State
from mavros_msgs.srv import CommandBool, SetMode


class UAVController:
    """单机控制类（与 dual_takeoff_test.py 中相同）"""

    def __init__(self, namespace):
        self.ns = namespace
        self.current_state = State()
        self.current_pose = PoseStamped()

        rospy.Subscriber(f'/{self.ns}/mavros/state', State, self._state_cb)
        rospy.Subscriber(
            f'/{self.ns}/mavros/local_position/pose',
            PoseStamped, self._pose_cb
        )
        self.pos_pub = rospy.Publisher(
            f'/{self.ns}/mavros/setpoint_position/local',
            PoseStamped, queue_size=10
        )
        rospy.wait_for_service(f'/{self.ns}/mavros/cmd/arming')
        rospy.wait_for_service(f'/{self.ns}/mavros/set_mode')
        self._arming_client = rospy.ServiceProxy(
            f'/{self.ns}/mavros/cmd/arming', CommandBool
        )
        self._set_mode_client = rospy.ServiceProxy(
            f'/{self.ns}/mavros/set_mode', SetMode
        )
        self.target = PoseStamped()
        self.target.pose.position.z = 2.0
        self.target.pose.orientation.w = 1.0
        rospy.loginfo(f"[{self.ns}] 控制接口初始化完成")

    def _state_cb(self, msg):
        self.current_state = msg

    def _pose_cb(self, msg):
        self.current_pose = msg

    @property
    def connected(self):
        return self.current_state.connected

    @property
    def armed(self):
        return self.current_state.armed

    @property
    def position(self):
        p = self.current_pose.pose.position
        return (p.x, p.y, p.z)

    def set_target(self, x, y, z):
        self.target.pose.position.x = x
        self.target.pose.position.y = y
        self.target.pose.position.z = z

    def publish_target(self):
        self.target.header.stamp = rospy.Time.now()
        self.pos_pub.publish(self.target)

    def arm(self):
        resp = self._arming_client(True)
        if resp.success:
            rospy.loginfo(f"[{self.ns}] 解锁成功")
        else:
            rospy.logerr(f"[{self.ns}] 解锁失败! result: {resp.result}")
        return resp.success

    def set_mode(self, mode):
        resp = self._set_mode_client(custom_mode=mode)
        if resp.mode_sent:
            rospy.loginfo(f"[{self.ns}] 模式切换请求已发送: {mode}")
        return resp.mode_sent


def main():
    rospy.init_node('formation_follow_test')
    rate = rospy.Rate(20)

    # ========== 创建控制实例 ==========
    leader = UAVController('iris_0')
    follower = UAVController('iris_1')
    uavs = [leader, follower]

    # ========== 坐标系参数 ==========
    spawn_offset_x = 3.0
    spawn_offset_y = 0.0
    spawn_offset_z = 0.0

    # 编队偏移量：从机在主机 x 正方向 2 米处
    formation_offset_x = 2.0
    formation_offset_y = 0.0
    formation_offset_z = 0.0

    def update_follower_target():
        lx, ly, lz = leader.position
        fx = lx + formation_offset_x - spawn_offset_x
        fy = ly + formation_offset_y - spawn_offset_y
        fz = lz + formation_offset_z - spawn_offset_z
        fz = max(fz, 1.5)
        follower.set_target(fx, fy, fz)

    # ========== 等待连接 ==========
    rospy.loginfo("等待所有飞机连接...")
    while not rospy.is_shutdown():
        if all(uav.connected for uav in uavs):
            break
        rate.sleep()
    rospy.loginfo("所有飞机已连接！")

    # ========== 设置初始目标并预喂 ==========
    leader.set_target(0.0, 0.0, 2.0)
    follower.set_target(
        0.0 + formation_offset_x - spawn_offset_x,
        0.0 + formation_offset_y - spawn_offset_y,
        max(2.0 + formation_offset_z - spawn_offset_z, 1.5)
    )

    rospy.loginfo("预喂 setpoint 5 秒...")
    for _ in range(100):
        if rospy.is_shutdown():
            return
        for uav in uavs:
            uav.publish_target()
        rate.sleep()

    # ========== 起飞 ==========
    for uav in uavs:
        uav.set_mode('OFFBOARD')
        uav.arm()

    # ========== 航点 1：原地起飞悬停 8 秒 ==========
    rospy.loginfo("=== 航点 1：起飞到 2 米悬停 ===")
    phase_start = rospy.Time.now()
    while not rospy.is_shutdown():
        if (rospy.Time.now() - phase_start).to_sec() >= 8.0:
            break
        update_follower_target()
        for uav in uavs:
            uav.publish_target()
        rate.sleep()
    lx, ly, lz = leader.position
    fx, fy, fz = follower.position
    rospy.loginfo(f"  主机位置: ({lx:.1f}, {ly:.1f}, {lz:.1f})")
    rospy.loginfo(f"  从机位置: ({fx:.1f}, {fy:.1f}, {fz:.1f})")

    # ========== 航点 2：主机前进到 (4, 0, 2) ==========
    rospy.loginfo("=== 航点 2：主机前进到 (4, 0, 2) ===")
    leader.set_target(4.0, 0.0, 2.0)
    phase_start = rospy.Time.now()
    while not rospy.is_shutdown():
        if (rospy.Time.now() - phase_start).to_sec() >= 8.0:
            break
        update_follower_target()
        for uav in uavs:
            uav.publish_target()
        rate.sleep()
    lx, ly, lz = leader.position
    fx, fy, fz = follower.position
    rospy.loginfo(f"  主机位置: ({lx:.1f}, {ly:.1f}, {lz:.1f})")
    rospy.loginfo(f"  从机位置: ({fx:.1f}, {fy:.1f}, {fz:.1f})")

    # ========== 航点 3：主机转向 (4, 4, 2) ==========
    rospy.loginfo("=== 航点 3：主机转向 (4, 4, 2) ===")
    leader.set_target(4.0, 4.0, 2.0)
    phase_start = rospy.Time.now()
    while not rospy.is_shutdown():
        if (rospy.Time.now() - phase_start).to_sec() >= 8.0:
            break
        update_follower_target()
        for uav in uavs:
            uav.publish_target()
        rate.sleep()
    lx, ly, lz = leader.position
    fx, fy, fz = follower.position
    rospy.loginfo(f"  主机位置: ({lx:.1f}, {ly:.1f}, {lz:.1f})")
    rospy.loginfo(f"  从机位置: ({fx:.1f}, {fy:.1f}, {fz:.1f})")

    # ========== 降落 ==========
    rospy.loginfo("=== 编队降落 ===")
    for uav in uavs:
        uav.set_mode('AUTO.LAND')

    rospy.loginfo("等待所有飞机降落完成...")
    while not rospy.is_shutdown():
        if not any(uav.armed for uav in uavs):
            break
        rate.sleep()

    rospy.loginfo("编队飞行测试完成！")


if __name__ == '__main__':
    try:
        main()
    except rospy.ROSInterruptException:
        pass
