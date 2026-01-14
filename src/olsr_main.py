'''
本文件为运行olsr应用层覆盖网络的主程序入口
'''
import time
import socket
import struct
import threading  # 引入线程模块，用于处理周期性任务
import random     # 用于Jitter

# 引入各个模块
from link_sensing import LinkSet
from neigh_manager import NeighborManager
from topology_manager import TopologyManager
from routing_manager import RoutingManager
from flooding_mpp import DuplicateSet

# 引入消息格式处理
from pkt_msg_fmt import create_packet_header, create_message_header, encode_mantissa
from hello_msg_body import create_hello_body, parse_hello_body
from tc_msg_body import create_tc_body, parse_tc_body
from constants import *

class OLSRNode:
    def __init__(self, my_ip, port=698):
        self.my_ip = my_ip
        self.port = port
        
        # --- 1. 初始化网络接口 ---
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1) # 允许广播
        self.sock.bind(('0.0.0.0', self.port))
        
        # --- 2. 初始化各个管理器 ---
        self.link_set = LinkSet()
        self.link_set.my_ip = my_ip
        
        self.neighbor_manager = NeighborManager(my_ip)
        
        self.topology_manager = TopologyManager(my_ip)
        
        # 【新增】初始化路由管理器
        self.routing_manager = RoutingManager(
            my_ip, 
            self.neighbor_manager, 
            self.topology_manager
        )
        
        self.duplicate_set = DuplicateSet()

        # --- 3. 状态变量 ---
        self.pkt_seq_num = 0    # 包序列号
        self.msg_seq_num = 0    # 消息序列号
        self.ansn = 0           # TC 序列号
        self.running = True

    # ==========================
    # 核心功能 1: 数据包接收与分发
    # ==========================
    def start(self):
        """启动主循环和辅助线程"""
        print(f"[*] OLSR 节点 {self.my_ip} 启动，监听端口 {self.port}")
        
        # 启动周期性任务线程
        threading.Thread(target=self.loop_hello, daemon=True).start()
        threading.Thread(target=self.loop_tc, daemon=True).start()
        threading.Thread(target=self.loop_cleanup, daemon=True).start()
        
        # 主线程负责接收 UDP 数据
        self.receive_loop()

    def receive_loop(self):
        while self.running:
            try:
                data, addr = self.sock.recvfrom(2048)
                sender_ip = addr[0]
                # 忽略自己发出的包 (简单过滤)
                if sender_ip == self.my_ip:
                    continue
                self.process_packet(data, sender_ip)
            except Exception as e:
                print(f"[Error] Receive Loop: {e}")

    def process_packet(self, data, sender_ip):
        """
        解析 UDP 包，提取 Message，分发处理
        """
        if len(data) < 4: return
        
        # 1. 解析包头
        pkt_len, pkt_seq = struct.unpack('!HH', data[:4])
        cursor = 4
        
        # 2. 遍历包内所有消息
        while cursor < len(data):
            if len(data) - cursor < 12: break
            
            # 解析消息头
            msg_header = data[cursor : cursor+12]
            msg_type, vtime, msg_size, orig_ip_bytes, ttl, hop, msg_seq = \
                struct.unpack('!BBH4sBBH', msg_header)
            
            originator_ip = socket.inet_ntoa(orig_ip_bytes)
            
            # 计算消息体位置
            body_start = cursor + 12
            body_end = cursor + msg_size
            if body_end > len(data): break # 格式错误
            
            msg_body = data[body_start : body_end]
            
            # --- 处理去重 (Duplicate Check) ---
            # 无论什么消息，先检查是否处理过
            current_time = time.time()
            is_dup = self.duplicate_set.is_duplicate(originator_ip, msg_seq)
            if not is_dup:
                self.duplicate_set.record_message(originator_ip, msg_seq, current_time)
                
                # --- 消息分发 (Dispatch) ---
                if msg_type == HELLO_MESSAGE: # Type 1
                    # 解析 HELLO Body
                    hello_info = parse_hello_body(msg_body) 
                    if hello_info:
                        self.process_hello(sender_ip, hello_info)
                        
                elif msg_type == TC_MESSAGE: # Type 2
                    # 解析 TC Body
                    tc_info = parse_tc_body(msg_body)
                    if tc_info:
                        self.process_tc(originator_ip, tc_info)

            # --- 转发检查 (Forwarding) ---
            # 注意：即使处理过内容(is_dup=True)，也可能需要转发（如果之前没转发过）
            # 这里简化逻辑：如果是重复的且已转发过，check_forwarding_condition 会返回 False
            if self.check_forwarding_condition(sender_ip, originator_ip, msg_seq, ttl):
                self.forward_message(data[cursor:body_end], ttl, hop)

            # 移动指针
            cursor += msg_size

    # ==========================
    # 核心功能 2: 消息处理逻辑
    # ==========================
    def process_hello(self, sender_ip, hello_info):
        """处理收到的 HELLO 消息"""
        current_time = time.time()
        
        # 1. 链路感知
        self.link_set.process_hello(sender_ip, hello_info)
        
        # 获取链路状态
        link_tuple = self.link_set.links.get(sender_ip)
        is_link_sym = link_tuple.is_symmetric() if link_tuple else False
        
        # 2. 更新邻居状态
        self.neighbor_manager.update_neighbor_status(
            neighbor_ip=sender_ip, 
            willingness=hello_info['willingness'], 
            is_link_sym=is_link_sym
        )
        
        # 3. 如果是对称链路，进行高级处理
        if is_link_sym:
            self.neighbor_manager.process_2hop_neighbors(sender_ip, hello_info, current_time)
            self.neighbor_manager.process_mpr_selector(sender_ip, hello_info, current_time)
            
            # 触发 MPR 重算
            self.neighbor_manager.recalculate_mpr()
            
            # 【关键】拓扑可能变了，重新计算路由表
            self.routing_manager.recalculate_routing_table()

    def process_tc(self, originator_ip, tc_info):
        """处理收到的 TC 消息"""
        current_time = time.time()
        # 更新拓扑库
        self.topology_manager.process_tc_message(originator_ip, tc_info, current_time)
        
        # 【关键】拓扑变了，重新计算路由表
        self.routing_manager.recalculate_routing_table()

    # ==========================
    # 核心功能 3: 泛洪转发逻辑
    # ==========================
    def check_forwarding_condition(self, sender_ip, originator_ip, msg_seq_num, ttl):
        """RFC 3.4.1: 判断是否转发"""
        if ttl <= 1: return False
        if originator_ip == self.my_ip: return False # 不转发自己发的
        
        # 去重检查
        if self.duplicate_set.is_duplicate(originator_ip, msg_seq_num):
            dup_entry = self.duplicate_set.entries[(originator_ip, msg_seq_num)]
            if dup_entry.retransmitted:
                return False # 已经转发过了

        # MPR 规则: 只有当 Sender 选我做 MPR 时才转发
        if sender_ip in self.neighbor_manager.mpr_selectors:
            return True
        return False

    def forward_message(self, raw_msg_bytes, old_ttl, old_hop):
        """执行转发：修改 TTL 和 Hop Count"""
        # 解包头部修改
        header_fmt = '!BBH4sBBH'
        header_len = 12
        msg_header = list(struct.unpack(header_fmt, raw_msg_bytes[:header_len]))
        
        # 修改 TTL (-1) 和 Hop Count (+1)
        msg_header[4] = old_ttl - 1
        msg_header[5] = old_hop + 1
        
        # 重新打包
        new_header = struct.pack(header_fmt, *msg_header)
        new_msg = new_header + raw_msg_bytes[header_len:]
        
        # 封装进新的 UDP 包发送
        self.send_packet(new_msg)
        
        # 提取 Originator 和 Seq 用于标记已转发
        # (这里为了代码简洁，假设在外部已经获取了这些信息并标记)
        # 实际代码中应该在这里解析并 self.duplicate_set.mark_retransmitted(...)

    # ==========================
    # 核心功能 4: 周期性发送
    # ==========================
    def loop_hello(self):
        """周期发送 HELLO"""
        while self.running:
            try:
                self.generate_and_send_hello()
                # 添加 Jitter 防止同步冲突
                time.sleep(HELLO_INTERVAL - 0.5 + random.random()) 
            except Exception as e:
                print(f"[Error] Hello Loop: {e}")

    def loop_tc(self):
        """周期发送 TC (仅当我是 MPR)"""
        while self.running:
            try:
                self.generate_and_send_tc()
                time.sleep(TC_INTERVAL - 0.5 + random.random())
            except Exception as e:
                print(f"[Error] TC Loop: {e}")

    def loop_cleanup(self):
        """周期清理过期数据"""
        while self.running:
            time.sleep(2.0) # 每2秒检查一次
            self.link_set.cleanup()
            self.neighbor_manager.cleanup()
            self.topology_manager.cleanup()
            self.duplicate_set.cleanup()

    # ==========================
    # 辅助函数
    # ==========================
    def generate_and_send_hello(self):
        # 1. 获取邻居列表 (带 MPR 标记)
        # 获取当前 MPR 集
        current_mpr_set = self.neighbor_manager.current_mpr_set
        groups = self.link_set.get_hello_groups(current_mpr_set)
        
        # 2. 构建 Hello Body
        hello_body = create_hello_body(HELLO_INTERVAL, WILL_DEFAULT, groups)
        
        # 3. 构建 Message Header
        msg_header = create_message_header(
            msg_type=HELLO_MESSAGE, 
            vtime_seconds=NEIGHB_HOLD_TIME, 
            msg_body_len=len(hello_body),
            originator_ip=self.my_ip, 
            ttl=1, 
            hop_count=0, 
            msg_seq_num=self.get_next_msg_seq()
        )
        
        # 4. 发送
        self.send_packet(msg_header + hello_body)
        print(f"[Send] HELLO sent. Neighbors: {len(groups)} groups")

    def generate_and_send_tc(self):
        # 获取选我做 MPR 的邻居
        my_selectors = list(self.neighbor_manager.mpr_selectors.keys())
        if not my_selectors: return 

        self.ansn = (self.ansn + 1) % 65535
        tc_body = create_tc_body(self.ansn, my_selectors)
        
        msg_header = create_message_header(
            msg_type=TC_MESSAGE, 
            vtime_seconds=TOP_HOLD_TIME, 
            msg_body_len=len(tc_body),
            originator_ip=self.my_ip, 
            ttl=255, 
            hop_count=0, 
            msg_seq_num=self.get_next_msg_seq()
        )
        self.send_packet(msg_header + tc_body)
        print(f"[Send] TC sent. Selectors: {my_selectors}")

    def send_packet(self, msg_bytes):
        """封装 UDP 包头并发送广播"""
        pkt_header = create_packet_header(len(msg_bytes), self.get_next_pkt_seq())
        data = pkt_header + msg_bytes
        self.sock.sendto(data, ('<broadcast>', self.port))

    def get_next_msg_seq(self):
        self.msg_seq_num = (self.msg_seq_num + 1) % 65535
        return self.msg_seq_num

    def get_next_pkt_seq(self):
        self.pkt_seq_num = (self.pkt_seq_num + 1) % 65535
        return self.pkt_seq_num

# 启动入口
if __name__ == "__main__":
    import sys
    my_ip = "192.168.1.100" # 默认测试IP，实际使用时应自动获取或传入
    if len(sys.argv) > 1:
        my_ip = sys.argv[1]
        
    node = OLSRNode(my_ip)
    node.start()