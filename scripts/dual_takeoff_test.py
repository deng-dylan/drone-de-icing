#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
两机独立控制测试脚本
功能：两架 iris 分别飞到不同高度，悬停后各自飞到不同的水平位置，最后同时降落
代码结构：单机控制类 + 多机管理器，为后续扩展打基础

架构说明：
  UAVController —— 封装单架无人机的所有控制逻辑（订阅、发布、模式切换、解锁）
                   通过 namespace 参数区分不同飞机，代码完全复用
  main()        —— 多机管理器的雏形，负责创建多个 UAVController 实例并编排任务
"""

import rospy
from geometry_msgs.msg import PoseStamped
from mavros_msgs.msg import State
from mavros_msgs.srv import CommandBool, SetMode


class UAVController:
    """
    单机控制类：封装一架无人机的全部控制接口。

    设计原则：
    - 所有话题和服务都通过 namespace 参数自动加前缀
    - 同一份代码可以控制 iris_0、iris_1、iris_2……任意编号的飞机
    - 对外暴露简洁的方法：wait_for_connection, set_target, arm, set_mode
    """

    def __init__(self, namespace):
        self.ns = namespace
        self.current_state = State()

        rospy.Subscriber(f'/{self.ns}/mavros/state', State, self._state_cb)
        self.pos_pub = rospy.Publisher(
            f'/{self.ns}/mavros/setpoint_position/local',
            PoseStamped, queue_size=10
        )

        rospy.loginfo(f"[{self.ns}] 等待 MAVROS 服务上线...")
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

    @property
    def connected(self):
        return self.current_state.connected

    @property
    def armed(self):
        return self.current_state.armed

    @property
    def mode(self):
        return self.current_state.mode

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
        else:
            rospy.logerr(f"[{self.ns}] 模式切换请求失败: {mode}")
        return resp.mode_sent


def main():
    rospy.init_node('dual_takeoff_test')
    rate = rospy.Rate(20)

    # ========== 创建两个控制实例 ==========
    uav0 = UAVController('iris_0')
    uav1 = UAVController('iris_1')
    uavs = [uav0, uav1]

    # ========== 等待所有飞机连接 ==========
    rospy.loginfo("等待所有飞机连接...")
    while not rospy.is_shutdown():
        if all(uav.connected for uav in uavs):
            break
        rate.sleep()
    rospy.loginfo("所有飞机已连接！")

    # ========== 设置各自的初始目标高度（不同！） ==========
    uav0.set_target(0.0, 0.0, 2.0)   # iris_0: 2 米高
    uav1.set_target(0.0, 0.0, 3.0)   # iris_1: 3 米高

    # ========== 预喂 setpoint 5 秒 ==========
    rospy.loginfo("预喂 setpoint 5 秒...")
    for _ in range(100):
        if rospy.is_shutdown():
            return
        for uav in uavs:
            uav.publish_target()
        rate.sleep()
    rospy.loginfo("预喂完成")

    # ========== 逐架切模式 + 解锁 ==========
    for uav in uavs:
        uav.set_mode('OFFBOARD')
        uav.arm()

    # ========== 阶段 1：各自起飞到不同高度，悬停 8 秒 ==========
    rospy.loginfo("=== 阶段 1：各自起飞到不同高度，悬停 8 秒 ===")
    rospy.loginfo("  iris_0 -> (0, 0, 2)")
    rospy.loginfo("  iris_1 -> (0, 0, 3)")
    phase_start = rospy.Time.now()
    while not rospy.is_shutdown():
        if (rospy.Time.now() - phase_start).to_sec() >= 8.0:
            break
        for uav in uavs:
            uav.publish_target()
        rate.sleep()

    # ========== 阶段 2：飞到不同的水平位置，悬停 8 秒 ==========
    rospy.loginfo("=== 阶段 2：飞到不同水平位置，悬停 8 秒 ===")
    uav0.set_target(2.0, 0.0, 2.0)
    uav1.set_target(-2.0, 0.0, 3.0)
    rospy.loginfo("  iris_0 -> (2, 0, 2)")
    rospy.loginfo("  iris_1 -> (-2, 0, 3)")
    phase_start = rospy.Time.now()
    while not rospy.is_shutdown():
        if (rospy.Time.now() - phase_start).to_sec() >= 8.0:
            break
        for uav in uavs:
            uav.publish_target()
        rate.sleep()

    # ========== 降落 ==========
    rospy.loginfo("=== 所有飞机降落 ===")
    for uav in uavs:
        uav.set_mode('AUTO.LAND')

    rospy.loginfo("等待所有飞机降落完成...")
    while not rospy.is_shutdown():
        if not any(uav.armed for uav in uavs):
            break
        rate.sleep()

    rospy.loginfo("所有飞机已降落！测试结束。")


if __name__ == '__main__':
    try:
        main()
    except rospy.ROSInterruptException:
        pass
