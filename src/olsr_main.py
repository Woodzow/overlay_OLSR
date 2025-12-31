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

from neigh_detec import NeighborTuple, TwoHopTuple, TopologyManager
from constants import *

# src/olsr_main.py
from link_sensing import LinkSet  # 引入你写好的 LinkSet 类
from neigh_detec import NeighborManager # 引入你写好的 NeighborManager 类

class OLSRNode:
    def __init__(self, my_ip):
        self.my_ip = my_ip
        # === 初始化各个管理器 ===
        self.link_set = LinkSet()               # 负责链路感知，linkset是没有参数传入的
        self.link_set.my_ip = my_ip             # 确保 LinkSet 知道本机 IP
        
        self.neighbor_manager = NeighborManager(my_ip) # 负责邻居和2跳
        # self.topology_manager = ... (未来扩展)

    def process_hello(self, sender_ip, hello_body):
        """
        总指挥：收到 HELLO 后，依次调度各个模块处理
        """
        current_time = time.time()

        # --- 1. 调度 LinkSet 处理链路 ---
        # 使用的是LinkSet类中的处理hello消息的方法
        self.link_set.process_hello(sender_ip, hello_body)
        
        # 获取刚刚更新后的链路状态，传给下一个模块
        # 注意：这里我们访问 link_set 内部的 links 字典
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

    def cleanup(self):
        """周期性清理任务"""
        self.link_set.cleanup()
        self.neighbor_manager.cleanup()


if __name__ == "main":