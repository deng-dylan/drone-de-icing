#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
单机起飞测试脚本
功能：连接 → 喂 setpoint → 切 OFFBOARD → 解锁 → 悬停 10 秒 → 降落
用途：验证单机控制链路是否稳定
"""

import rospy
from geometry_msgs.msg import PoseStamped
from mavros_msgs.msg import State
from mavros_msgs.srv import CommandBool, SetMode

# ========== 全局状态 ==========
current_state = State()

def state_callback(msg):
    """实时更新无人机状态"""
    global current_state
    current_state = msg

def main():
    rospy.init_node('single_takeoff_test')
    rate = rospy.Rate(20)  # 20Hz，PX4 要求 OFFBOARD 至少 2Hz

    # ---------- 订阅状态 ----------
    rospy.Subscriber('/mavros/state', State, state_callback)

    # ---------- 发布目标位置 ----------
    local_pos_pub = rospy.Publisher(
        '/mavros/setpoint_position/local', PoseStamped, queue_size=10
    )

    # ---------- 服务客户端 ----------
    rospy.loginfo("等待 MAVROS 服务上线...")
    rospy.wait_for_service('/mavros/cmd/arming')
    rospy.wait_for_service('/mavros/set_mode')
    arming_client = rospy.ServiceProxy('/mavros/cmd/arming', CommandBool)
    set_mode_client = rospy.ServiceProxy('/mavros/set_mode', SetMode)

    # ---------- 等待 MAVROS 连接 ----------
    rospy.loginfo("等待 MAVROS 连接 PX4...")
    while not rospy.is_shutdown() and not current_state.connected:
        rate.sleep()
    rospy.loginfo("MAVROS 已连接！当前模式: %s", current_state.mode)

    # ---------- 构造目标点：原地上方 2 米 ----------
    target_pose = PoseStamped()
    target_pose.pose.position.x = 0.0
    target_pose.pose.position.y = 0.0
    target_pose.pose.position.z = 2.0
    target_pose.pose.orientation.w = 1.0

    # ---------- 预喂 setpoint：必须持续发 5 秒 ----------
    # PX4 规则：OFFBOARD 模式要求切换前至少连续收到 2 秒的 setpoint
    # 我们给 5 秒，留足余量
    rospy.loginfo("开始预喂 setpoint，持续 5 秒...")
    for i in range(100):  # 20Hz × 5秒 = 100 次
        if rospy.is_shutdown():
            return
        target_pose.header.stamp = rospy.Time.now()  # 关键：用当前时间戳！
        local_pos_pub.publish(target_pose)
        rate.sleep()
    rospy.loginfo("预喂完成。")

    # ---------- 切换到 OFFBOARD 模式 ----------
    rospy.loginfo("切换到 OFFBOARD 模式...")
    resp = set_mode_client(custom_mode='OFFBOARD')
    if resp.mode_sent:
        rospy.loginfo("OFFBOARD 模式请求已发送")
    else:
        rospy.logerr("OFFBOARD 模式请求失败！")
        return

    # ---------- 解锁 ----------
    rospy.loginfo("解锁电机...")
    resp = arming_client(True)
    if resp.success:
        rospy.loginfo("解锁成功！无人机应该开始起飞了")
    else:
        rospy.logerr("解锁失败！result: %d", resp.result)
        return

    # ---------- 悬停阶段：持续发 setpoint 保持 OFFBOARD ----------
    # 如果停止发送 setpoint，PX4 会在 0.5 秒内触发失控保护
    hover_duration = 10  # 悬停 10 秒
    rospy.loginfo("悬停 %d 秒...", hover_duration)
    hover_start = rospy.Time.now()
    while not rospy.is_shutdown():
        elapsed = (rospy.Time.now() - hover_start).to_sec()
        if elapsed >= hover_duration:
            break
        target_pose.header.stamp = rospy.Time.now()
        local_pos_pub.publish(target_pose)
        rate.sleep()

    # ---------- 降落 ----------
    rospy.loginfo("切换到 AUTO.LAND 模式，开始降落...")
    set_mode_client(custom_mode='AUTO.LAND')

    # 等待降落完成（检测 armed 状态变为 False）
    rospy.loginfo("等待降落完成...")
    while not rospy.is_shutdown() and current_state.armed:
        rate.sleep()

    rospy.loginfo("降落完成！测试结束。")

if __name__ == '__main__':
    try:
        main()
    except rospy.ROSInterruptException:
        pass
