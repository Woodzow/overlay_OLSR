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

class OLSRNode:
    def __init__(self, my_ip):
        self.my_ip = my_ip
        
        # === 这里的字典就是所谓的“信息库(Information Repositories)” ===
        self.links = {}      # 存储 LinkTuple,链路信息
        self.neighbors = {}  # 存储 NeighborTuple ,邻居信息
        self.two_hop_set = {} # 存储 2-hop Tuple ，两跳邻居信息

    
    def update_neighbor_set(self, neighbor_ip, willingness, is_link_sym):
        """
        根据链路状态更新邻居集 (RFC Section 8.1)
        """
        # 1. 如果邻居不存在，创建它 [cite: 878-880]
        if neighbor_ip not in self.neighbors:
            self.neighbors[neighbor_ip] = NeighborTuple(neighbor_ip)
        
        neigh = self.neighbors[neighbor_ip]
        
        # 2. 更新意愿值 
        neigh.willingness = willingness
        
        # 3. 更新状态 (N_status) [cite: 885-887]
        # 只要有一个对称链路，邻居状态就是 SYM
        if is_link_sym:
            neigh.status = 1 # SYM_NEIGH
        else:
            neigh.status = 0 # NOT_NEIGH
            
        print(f"[NeighborSet] 更新邻居 {neighbor_ip}: Status={neigh.status}, Will={neigh.willingness}")

    def process_hello(self, sender_ip, hello_body):
        """
        处理收到 HELLO 消息的入口
        """
        # --- 步骤 1: 链路感知 (Link Sensing) ---
        # (这里是你之前写的 LinkSet 更新逻辑，略...)
        # 假设它返回一个布尔值，告诉我们要不要把这个链路当成对称的
        # link_is_sym = self.link_set_manager.process(...) 
        # 或者直接写在这里
        
        # 假设经过判断，链路是对称的 (current_time < L_SYM_time)
        link_is_sym = True # 这里应该是你算出来的结果
        
        # --- 步骤 2: 邻居检测 (Neighbor Detection) ---
        # 调用上面的方法更新 NeighborTuple
        self.update_neighbor_set(sender_ip, hello_body['willingness'], link_is_sym)

        # --- 步骤 3: 2跳邻居检测 ---
        # (下一步要做的事)
        def process_2hop_neighbors(self, sender_ip, hello_body, current_time):
        """
        处理 HELLO 消息以更新 2跳邻居集
        参考 RFC 3626 Section 8.2.1
        """
        validity_time = hello_body['htime_seconds'] * 3
        
        # 1. 遍历 HELLO 里的所有邻居组
        for link_code, ip_list in hello_body['neighbor_groups']:
            # 解析 Link Code
            # Bit 2-3 是 Neighbor Type [cite: 677]
            neigh_type = (link_code >> 2) & 0x03
            
            # RFC 8.2.1 rule 1: 必须是 SYM_NEIGH (1) 或 MPR_NEIGH (2)
            # 这意味着发送者和这些人是通的
            if neigh_type == 1 or neigh_type == 2:
                for two_hop_ip in ip_list:
                    # RFC 8.2.1 rule 1.1: 2跳邻居不能是我自己 [cite: 926-927]
                    if two_hop_ip == self.my_ip:
                        continue
                    
                    # RFC 8.2.1 rule 1.2: 创建或更新 2跳元组 [cite: 929-937]
                    key = (sender_ip, two_hop_ip)
                    
                    if key not in self.two_hop_set:
                        print(f"[2-Hop] 发现新 2跳节点: 我 -> {sender_ip} -> {two_hop_ip}")
                        self.two_hop_set[key] = TwoHopTuple(sender_ip, two_hop_ip)
                    
                    # 更新过期时间
                    self.two_hop_set[key].expiration_time = current_time + validity_time

            # RFC 8.2.1 rule 2: 如果对方说 "NOT_NEIGH"，我们需要删除对应的记录 [cite: 939-943]
            elif neigh_type == 0: # NOT_NEIGH
                for two_hop_ip in ip_list:
                    key = (sender_ip, two_hop_ip)
                    if key in self.two_hop_set:
                        print(f"[2-Hop] 链路断开，删除 2跳: {sender_ip} -x-> {two_hop_ip}")
                        del self.two_hop_set[key]

    def cleanup_2hop(self):
        """清理过期记录"""
        now = time.time()
        keys_to_remove = [k for k, v in self.two_hop_set.items() if v.expiration_time < now]
        for k in keys_to_remove:
            del self.two_hop_set[k]



if __name__ == "main":