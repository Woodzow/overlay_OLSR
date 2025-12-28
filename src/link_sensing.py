import time
import socket
from constants import *

class LinkTuple:
    def __init__(self, neighbor_ip):
        self.neighbor_ip = neighbor_ip
        self.l_asym_time = 0  # 异步过期时间戳
        self.l_sym_time = 0   # 对称过期时间戳
        self.l_time = 0       # 记录过期时间戳 (通常取上面两者的最大值 + 保持时间)

    def is_symmetric(self):
        """判断当前链路是否对称"""
        return time.time() < self.l_sym_time

    def is_asymmetric(self):
        """判断当前链路是否仅为非对称（我听到他，但他没听到我）"""
        return (time.time() < self.l_asym_time) and (not self.is_symmetric())

# 类似于邻居数据库的类来存储链路信息，操作信息的增删  
# 常量定义 (基于 RFC 18.3)
NEIGHB_HOLD_TIME = 6.0  # 3 * HELLO_INTERVAL

class LinkSet:
    def __init__(self):
        self.links = {}  # 格式: { '192.168.1.5': LinkTuple对象, ... }
        self.my_ip = "192.168.1.100" # 请替换为你的真实IP

    def process_hello(self, sender_ip, hello_body):
        """
        核心逻辑：根据收到的 HELLO 处理链路状态
        参考 RFC 3626 Section 7.1.1
        """
        current_time = time.time()
        validity_time = hello_body['htime_seconds'] * 3 # 通常 Validity Time = 3 * Htime [cite: 1685, 1710]

        # 1. 如果是新邻居，创建记录 [cite: 816-827]
        if sender_ip not in self.links:
            print(f"[LinkSet] 发现新邻居: {sender_ip}")
            new_link = LinkTuple(sender_ip)
            # 新邻居默认为非对称，L_SYM_time 设为过期
            new_link.l_sym_time = current_time - 1 
            self.links[sender_ip] = new_link
        
        link = self.links[sender_ip]

        # 2. 更新 L_ASYM_time (只要收到 Hello 就更新) [cite: 831-832]
        link.l_asym_time = current_time + validity_time
        
        # 3. 检查对方是否听到了我 (链路是否对称?) [cite: 834-835]
        # 遍历 Hello 消息里的所有邻居组
        found_myself = False
        for link_code, ip_list in hello_body['neighbor_groups']:
            if self.my_ip in ip_list:
                found_myself = True
                # 检查对方标记的链路类型
                l_type = link_code & 0x03
                if l_type == 3: # LOST_LINK [cite: 842]
                    link.l_sym_time = current_time - 1 # 对方说丢失了，我们也标记为非对称
                elif l_type == 1 or l_type == 2: # ASYM_LINK or SYM_LINK [cite: 846]
                    link.l_sym_time = current_time + validity_time # 确认为对称！
                    print(f"[LinkSet] 与 {sender_ip} 建立对称链路！")
                break
        
        # 4. 更新记录总过期时间 L_time [cite: 848-850]
        link.l_time = max(link.l_sym_time, link.l_asym_time) + NEIGHB_HOLD_TIME

    def cleanup(self):
        """定期清理过期邻居"""
        current_time = time.time()
        expired_ips = [ip for ip, link in self.links.items() if link.l_time < current_time]
        for ip in expired_ips:
            print(f"[LinkSet] 邻居 {ip} 已过期，删除记录。")
            del self.links[ip]

#基于链路状态生成hello消息相关内容
def get_hello_groups(self):
        """
        根据当前 LinkSet 生成用于发送 HELLO 的 neighbor_groups
        参考 RFC 3626 Section 6.2
        """
        sym_neighbors = []
        asym_neighbors = []
        
        current_time = time.time()
        
        # 遍历所有邻居，分类
        for link in self.links.values():
            if link.l_time < current_time:
                continue # 已过期忽略
            
            if link.is_symmetric():
                sym_neighbors.append(link.neighbor_ip)
            elif link.is_asymmetric():
                asym_neighbors.append(link.neighbor_ip)
        
        groups = []
        # 1. 对称邻居组 (Link Type = SYM_LINK, Neighbor Type = SYM_NEIGH)
        if sym_neighbors:
            # create_link_code 需要你自己引入之前定义的函数
            code = create_link_code(2, 1) # SYM_LINK(2), SYM_NEIGH(1)
            groups.append((code, sym_neighbors))
            
        # 2. 非对称邻居组 (Link Type = ASYM_LINK, Neighbor Type = NOT_NEIGH)
        # 告诉对方：我听到了你，但还不知道你听到我没
        if asym_neighbors:
            code = create_link_code(1, 0) # ASYM_LINK(1), NOT_NEIGH(0)
            groups.append((code, asym_neighbors))
            
        return groups