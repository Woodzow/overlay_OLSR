'''
本文件为运行olsr应用层覆盖网络的主程序入口
'''
import time
import networkx
import heapq
import socket
import struct


import networkx as nx
import matplotlib as plt

from neigh_manager import NeighborTuple, TwoHopTuple, TopologyManager
from constants import *

# src/olsr_main.py
from link_sensing import LinkSet  # 引入你写好的 LinkSet 类
from neigh_manager import NeighborManager # 引入你写好的 NeighborManager 类
from flooding_mpp import DuplicateSet  # 引入你写好的 DuplicateSet 类

from tc_msg_body import create_tc_body, parse_tc_body
from topology_manager import TopologyManager
from pkt_msg_fmt import create_message_header

class OLSRNode:
    def __init__(self, my_ip):
        self.my_ip = my_ip
        # === 初始化各个管理器 ===
        self.link_set = LinkSet()               # 负责链路感知，linkset类是没有参数传入的
        self.link_set.my_ip = my_ip             # 确保 LinkSet 知道本机 IP
        
        self.neighbor_manager = NeighborManager(my_ip) # 负责邻居和2跳
        # self.topology_manager = ... (未来扩展)

        self.duplicate_set = DuplicateSet()  # 新增
        self.seq_number = 0 # 维护自己的发包序列号

        self.topology_manager = TopologyManager(my_ip)
        self.ansn = 0 # 维护自己的 TC 序列号


    def process_hello(self, sender_ip, hello_body):
        """
        总指挥：收到 HELLO 后，依次调度各个模块处理
        """
        current_time = time.time()

        # --- 1. 调度 LinkSet 处理链路 ---
        # 调用的是LinkSet类中的处理hello消息的方法
        self.link_set.process_hello(sender_ip, hello_body)
        
        # 获取刚刚更新后的链路状态，传给下一个模块
        # 注意：这里我们访问 link_set 内部的 .links 字典,取出里面的值，也就是LinkTuple对象类
        link_tuple = self.link_set.links.get(sender_ip)
        is_link_sym = link_tuple.is_symmetric() if link_tuple else False
        
        # --- 2. 调度 NeighborManager 更新 1跳邻居 ---
        self.neighbor_manager.update_neighbor_status(
            neighbor_ip=sender_ip, 
            willingness=hello_body['willingness'], 
            is_link_sym=is_link_sym
        )

        # --- 3. 调度 NeighborManager 处理 2跳邻居 ---
        # 只有当链路是对称的时候，才处理 2跳信息
        if is_link_sym:
            self.neighbor_manager.process_2hop_neighbors(sender_ip, hello_body, current_time)
        # 【新增】检查我是否被选为 MPR
            self.neighbor_manager.process_mpr_selector(sender_ip, hello_body, current_time)
            
            # 【新增】触发 MPR 重算 (只有当邻居拓扑变化时才需要，但每收到包算一次比较简单)
            self.neighbor_manager.recalculate_mpr()
    
    def check_forwarding_condition(self, sender_ip, originator_ip, msg_seq_num, ttl):
        """
        判断是否需要转发这条消息
        :param sender_ip: 上一跳是谁 (直连邻居 IP)
        :param originator_ip: 消息最初是谁发的 (源 IP)
        """
        # 1. 基本检查
        if ttl <= 1: 
            return False # TTL 耗尽，不转发
        if originator_ip == self.my_ip: 
            return False # 我自己发的消息转了一圈回来了，不转发

        # 2. 去重检查 (RFC 3.4.1 Step 2)
        # 如果已经在 Duplicate Set 里，且已经被标记为 retransmitted，则不转发
        if self.duplicate_set.is_duplicate(originator_ip, msg_seq_num):
            dup_entry = self.duplicate_set.entries[(originator_ip, msg_seq_num)]
            if dup_entry.retransmitted:
                return False

        # 3. MPR 转发规则 (RFC 3.4.1 Step 4) 
        # 只有当 "上一跳 (Sender)" 选我做了 MPR，我才帮忙转发
        # 注意：这里查的是 MPR Selectors (谁选了我)，而不是我选了谁
        is_selector = sender_ip in self.neighbor_manager.mpr_selectors
        
        if is_selector:
            return True
        else:
            return False

    def forward_message(self, raw_message_bytes):
        """
        执行实际的转发操作
        1. TTL - 1
        2. Hop Count + 1
        3. 广播出去
        """
        # 这里需要对二进制数据进行修改 (TTL位置), 比较繁琐
        # 建议先解包修改字段，再重新打包发送
        # 或者直接操作 bytes 数组的特定偏移量 (Message Header 第 9 字节是 TTL)
        pass
    

    def generate_and_send_tc(self):
        """
        构建并发送 TC 消息 (仅当我是 MPR 时)
        """
        # 获取我的 MPR Selectors (谁选了我做中继)
        # 注意：这需要你的 NeighborManager 有 mpr_selectors 属性
        my_selectors = list(self.neighbor_manager.mpr_selectors.keys())
        
        if not my_selectors:
            return # 如果没人选我，我就不发 TC (优化)

        # 更新序列号
        self.ansn = (self.ansn + 1) % 65535
        
        # 1. 构建 Body
        tc_body = create_tc_body(self.ansn, my_selectors)
        
        # 2. 构建 Message Header (Type=2, TTL=255 全网泛洪)
        msg_header = create_message_header(
            msg_type=2, 
            vtime_seconds=15.0, 
            msg_body_len=len(tc_body),
            originator_ip=self.my_ip, 
            ttl=255, 
            hop_count=0, 
            msg_seq_num=self.get_next_seq()
        )
        
        # 3. 发送 (广播)
        self.send_packet(msg_header + tc_body)





    def cleanup(self):
        """周期性清理任务"""
        self.link_set.cleanup()
        self.neighbor_manager.cleanup()


#if __name__ == "main":