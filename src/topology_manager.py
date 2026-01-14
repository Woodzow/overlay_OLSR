import time
from constants import TOP_HOLD_TIME # 通常是 15秒 (3 * TC_INTERVAL)

class TopologyTuple:
    def __init__(self, dest_addr, last_addr, seq):
        self.dest_addr = dest_addr  # 目标节点 (T_dest_addr)
        self.last_addr = last_addr  # 上一跳/网关节点 (T_last_addr)
        self.seq = seq              # 序列号 (T_seq)
        self.expiration_time = 0    # 过期时间 (T_time)

class TopologyManager:
    def __init__(self, my_ip):
        self.my_ip = my_ip
        # 拓扑集: 存储 TopologyTuple
        # 格式建议: {(dest_ip, last_ip): TopologyTuple} 
        # 这样可以通过 (目标, 源) 唯一确定一条链路
        self.topology_set = {} 

        #这里topology_set的key是(dest_addr, last_addr)的tuple，value是TopologyTuple对象
        #dest_addr (目标): 被宣告的邻居 IP（即 MPR Selector，接收广播的节点）。
        #last_addr (源/上一跳): 发送 TC 消息的节点 IP（即 MPR，宣告这条链路的节点）。

    def process_tc_message(self, originator_ip, tc_body, current_time):
        """
        处理接收到的 TC 消息，更新拓扑集 (RFC 9.5)
        :param originator_ip: TC 消息的发送源 (Message Header 里的 Originator)
        :param tc_body: 解析后的字典 {'ansn': ..., 'neighbors': ...}
        """
        # 1. 验证 ANSN (Advertised Neighbor Sequence Number)
        # 我们需要检查是否已经收到过这个 Originator 发来的更新的 TC
        # RFC 规则：如果内存里有比当前包更新的 ANSN，丢弃当前包
        
        # 这里的逻辑稍微有点绕：我们需要找到所有 T_last_addr == originator_ip 的记录
        # 来对比 sequence number。
        
        last_known_seq = -1
        # 遍历查找该源节点的已知最大序列号 (这不是最高效的写法，但最直观)
        for t_tuple in self.topology_set.values():
            if t_tuple.last_addr == originator_ip:
                last_known_seq = t_tuple.seq
                break # 通常同一个源节点的 seq 是一致的，找到一个就行

        received_seq = tc_body['ansn']

        # 序列号比较 (需考虑 RFC 19 的 Wrap-around，这里简化处理)
        # 如果收到的序列号 < 已知的序列号，说明是过时消息，丢弃
        if last_known_seq != -1 and received_seq < last_known_seq:
             # 注意：正式实现需处理 sequence number wrap-around (0xFFFF -> 0)
             print(f"[Topology] 收到过时 TC ({originator_ip}), 忽略。")
             return

        # 2. 如果收到的 TC 序列号更新 (received_seq > last_known_seq)
        # 删除旧的拓扑记录 (RFC 9.5 Rule 3)
        if received_seq > last_known_seq:
            keys_to_remove = []
            for key, t_tuple in self.topology_set.items():
                if t_tuple.last_addr == originator_ip:
                    keys_to_remove.append(key)
            
            for k in keys_to_remove:
                del self.topology_set[k]

        # 3. 添加/更新新的拓扑记录 (RFC 9.5 Rule 4)
        # T_dest_addr = TC 里的邻居 IP
        # T_last_addr = TC 的 Originator
        validity_time = TOP_HOLD_TIME # 应该从 Message Header 的 Vtime 获取，这里简化使用常量
        
        for neighbor_ip in tc_body['advertised_neighbors']:
            key = (neighbor_ip, originator_ip)
            
            if key not in self.topology_set:
                # 创建新记录
                t_tuple = TopologyTuple(neighbor_ip, originator_ip, received_seq)
                self.topology_set[key] = t_tuple
                print(f"[Topology] 新增链路: {originator_ip} -> {neighbor_ip}")
            else:
                # 更新现有记录
                t_tuple = self.topology_set[key]
                t_tuple.seq = received_seq
            
            # 刷新过期时间
            t_tuple.expiration_time = current_time + validity_time

    def cleanup(self):
        """清理过期拓扑"""
        now = time.time()
        keys_to_remove = [k for k, v in self.topology_set.items() if v.expiration_time < now]
        for k in keys_to_remove:
            del self.topology_set[k]