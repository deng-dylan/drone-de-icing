#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
五环表演脚本 - Five Ring Air Show

五架无人机从五环阵型出发，完成以下表演：
  1. 逐架起飞（像接力一样，一架架升空）
  2. 散开飞到远处高处，排成一条直线
  3. 保持队列在空中画一个正方形
  4. 回到各自的五环起始位置
  5. 逐架降落
"""

import rospy
from geometry_msgs.msg import PoseStamped
from mavros_msgs.msg import State
from mavros_msgs.srv import CommandBool, SetMode


class UAVController:
    """单机控制类：通过 namespace 区分不同飞机，一份代码控制任意数量的飞机。"""

    def __init__(self, namespace, spawn_x, spawn_y, spawn_z=0.0):
        self.ns = namespace
        self.spawn = (spawn_x, spawn_y, spawn_z)
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
        self.target.pose.orientation.w = 1.0
        rospy.loginfo(f"[{self.ns}] 初始化完成 (spawn: {spawn_x}, {spawn_y})")

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
    def local_position(self):
        p = self.current_pose.pose.position
        return (p.x, p.y, p.z)

    @property
    def world_position(self):
        lx, ly, lz = self.local_position
        return (lx + self.spawn[0], ly + self.spawn[1], lz + self.spawn[2])

    def set_target_world(self, wx, wy, wz):
        self.target.pose.position.x = wx - self.spawn[0]
        self.target.pose.position.y = wy - self.spawn[1]
        self.target.pose.position.z = max(wz - self.spawn[2], 1.0)

    def set_target_local(self, x, y, z):
        self.target.pose.position.x = x
        self.target.pose.position.y = y
        self.target.pose.position.z = max(z, 1.0)

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
        return resp.mode_sent


def publish_all(uavs):
    for uav in uavs:
        uav.publish_target()


def wait_phase(uavs, rate, duration, label=""):
    if label:
        rospy.loginfo(label)
    t0 = rospy.Time.now()
    while not rospy.is_shutdown():
        if (rospy.Time.now() - t0).to_sec() >= duration:
            break
        publish_all(uavs)
        rate.sleep()


def main():
    rospy.init_node('five_ring_show')
    rate = rospy.Rate(20)

    # 五环阵型：出生位置定义
    spawn_positions = [
        ('iris_0', 0.0,  0.0),
        ('iris_1', 3.0,  0.0),
        ('iris_2', 6.0,  0.0),
        ('iris_3', 1.5, -2.5),
        ('iris_4', 4.5, -2.5),
    ]

    uavs = []
    for ns, sx, sy in spawn_positions:
        uavs.append(UAVController(ns, sx, sy))

    # 等待所有飞机连接
    rospy.loginfo("等待所有飞机连接...")
    while not rospy.is_shutdown():
        if all(uav.connected for uav in uavs):
            break
        rate.sleep()
    rospy.loginfo("5 架飞机全部连接成功！")

    # 阶段参数
    HOVER_Z = 2.5
    LINE_Y = 20.0
    LINE_Z = 6.0
    LINE_SPACING = 5.0
    line_positions = [(i * LINE_SPACING, LINE_Y, LINE_Z) for i in range(5)]
    SQ = 8.0
    square_offsets = [
        (0, SQ, 0), (SQ, 0, 0), (0, -SQ, 0), (-SQ, 0, 0),
    ]
    home_positions = [(sx, sy, HOVER_Z) for _, sx, sy in spawn_positions]

    # 阶段 0：设置初始目标 + 预喂
    for i, uav in enumerate(uavs):
        uav.set_target_world(*home_positions[i])

    rospy.loginfo("预喂 setpoint 5 秒...")
    wait_phase(uavs, rate, 5.0)

    # 阶段 1：逐架起飞
    rospy.loginfo("")
    rospy.loginfo("=" * 50)
    rospy.loginfo("  阶段 1：逐架起飞（五环升空）")
    rospy.loginfo("=" * 50)

    for i, uav in enumerate(uavs):
        rospy.loginfo(f"  >>> {uav.ns} 起飞！")
        uav.set_mode('OFFBOARD')
        uav.arm()
        wait_phase(uavs, rate, 3.0)

    wait_phase(uavs, rate, 5.0, "  所有飞机已起飞，稳定悬停中...")

    for uav in uavs:
        wx, wy, wz = uav.world_position
        rospy.loginfo(f"  {uav.ns} 世界坐标: ({wx:.1f}, {wy:.1f}, {wz:.1f})")

    # 阶段 2：散开排成一字
    rospy.loginfo("")
    rospy.loginfo("=" * 50)
    rospy.loginfo("  阶段 2：散开排成一条直线")
    rospy.loginfo("=" * 50)

    for i, uav in enumerate(uavs):
        wx, wy, wz = line_positions[i]
        uav.set_target_world(wx, wy, wz)
        rospy.loginfo(f"  {uav.ns} -> 世界坐标 ({wx:.0f}, {wy:.0f}, {wz:.0f})")

    wait_phase(uavs, rate, 12.0)
    wait_phase(uavs, rate, 3.0, "  一字排开完成，稳定中...")

    for uav in uavs:
        wx, wy, wz = uav.world_position
        rospy.loginfo(f"  {uav.ns} 实际位置: ({wx:.1f}, {wy:.1f}, {wz:.1f})")

    # 阶段 3：空中画正方形
    rospy.loginfo("")
    rospy.loginfo("=" * 50)
    rospy.loginfo("  阶段 3：空中画正方形")
    rospy.loginfo("=" * 50)

    current_targets = list(line_positions)
    side_names = ["前进（y+8）", "右移（x+8）", "后退（y-8）", "左移（x-8）"]

    for side_idx, (dx, dy, dz) in enumerate(square_offsets):
        new_targets = []
        for i, (cx, cy, cz) in enumerate(current_targets):
            nx, ny, nz = cx + dx, cy + dy, cz + dz
            new_targets.append((nx, ny, nz))
            uavs[i].set_target_world(nx, ny, nz)
        current_targets = new_targets

        rospy.loginfo(f"  正方形第 {side_idx+1} 边：{side_names[side_idx]}")
        wait_phase(uavs, rate, 8.0)

        for uav in uavs:
            wx, wy, wz = uav.world_position
            rospy.loginfo(f"    {uav.ns}: ({wx:.1f}, {wy:.1f}, {wz:.1f})")

    rospy.loginfo("  正方形绘制完成！")

    # 阶段 4：回到五环位置
    rospy.loginfo("")
    rospy.loginfo("=" * 50)
    rospy.loginfo("  阶段 4：回到五环位置")
    rospy.loginfo("=" * 50)

    for i, uav in enumerate(uavs):
        wx, wy, wz = home_positions[i]
        uav.set_target_world(wx, wy, wz)
        rospy.loginfo(f"  {uav.ns} -> 回家 ({wx:.1f}, {wy:.1f}, {wz:.1f})")

    wait_phase(uavs, rate, 15.0)
    wait_phase(uavs, rate, 3.0, "  回到五环位置，稳定中...")

    for uav in uavs:
        wx, wy, wz = uav.world_position
        rospy.loginfo(f"  {uav.ns} 实际位置: ({wx:.1f}, {wy:.1f}, {wz:.1f})")

    # 阶段 5：逐架降落
    rospy.loginfo("")
    rospy.loginfo("=" * 50)
    rospy.loginfo("  阶段 5：逐架降落")
    rospy.loginfo("=" * 50)

    for uav in reversed(uavs):
        rospy.loginfo(f"  >>> {uav.ns} 降落")
        uav.set_mode('AUTO.LAND')
        wait_phase([u for u in uavs if u.armed], rate, 2.0)

    rospy.loginfo("  等待所有飞机落地...")
    while not rospy.is_shutdown():
        if not any(uav.armed for uav in uavs):
            break
        rate.sleep()

    rospy.loginfo("")
    rospy.loginfo("=" * 50)
    rospy.loginfo("  五环表演结束！")
    rospy.loginfo("=" * 50)


if __name__ == '__main__':
    try:
        main()
    except rospy.ROSInterruptException:
        pass
