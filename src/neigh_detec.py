import time



# from neigh_detec import NeighborTuple, TwoHopTuple 

class NeighborTuple:
    def __init__(self, main_addr):
        self.main_addr = main_addr
        self.status = 0         # 0: NOT_SYM, 1: SYM
        self.willingness = 3    # 默认 WILL_DEFAULT

class TwoHopTuple:
    def __init__(self, neighbor_main_addr, two_hop_addr):
        self.neighbor_main_addr = neighbor_main_addr  # 中间跳邻居
        self.two_hop_addr = two_hop_addr              # 二跳邻居
        self.expiration_time = 0                      # 过期时间？

# 管理一跳邻居节点以及二跳邻居
class NeighborManager:
    def __init__(self, my_ip):
        self.my_ip = my_ip
        self.neighbors = {}      # { 'ip': NeighborTuple }
        self.two_hop_set = {}    # { ('neighbor_ip', 'two_hop_ip'): TwoHopTuple }

    def update_neighbor_status(self, neighbor_ip, willingness, is_link_sym):
        """
        这里只是更新邻居状态
        根据链路状态更新邻居集 (RFC Section 8.1) 而链路状态是根据hello消息来更新的
        参数来源：
        - neighbor_ip: 来自 sender_ip
        - willingness: 来自 hello_body['willingness']
        - is_link_sym: 来自 LinkTuple.is_symmetric()
        """
        if neighbor_ip not in self.neighbors:# 判断某邻居ip是不是在neighbors这个字典的键里面
            self.neighbors[neighbor_ip] = NeighborTuple(neighbor_ip) #不在的话就用这个ip生成一个邻居元组作为值放到邻居节点的字典里面去
        
        neigh = self.neighbors[neighbor_ip]# 取出邻居tuple，然后更新传入参数对应的几个值
        neigh.willingness = willingness
        
        # 只要有一个对称链路，邻居状态就是 SYM
        if is_link_sym:
            neigh.status = 1 # SYM_NEIGH
        else:
            neigh.status = 0 # NOT_NEIGH
            
        print(f"[NeighborSet] 更新邻居 {neighbor_ip}: Status={neigh.status}, Will={neigh.willingness}")

    def process_2hop_neighbors(self, sender_ip, hello_info, current_time):
        """
        处理 HELLO 消息(中的neighbor_groups)以更新 2跳邻居集
        """
        validity_time = hello_info['htime_seconds'] * 3
        
        for link_code, ip_list in hello_info['neighbor_groups']:
            # 解析 Link Code (Bit 2-3 是 Neighbor Type)
            neigh_type = (link_code >> 2) & 0x03
            
            # 规则 1: 必须是 SYM_NEIGH(1) 或 MPR_NEIGH(2)
            if neigh_type == 1 or neigh_type == 2:
                for two_hop_ip in ip_list:
                    if two_hop_ip == self.my_ip: continue # 排除自己
                    #否则的话就是自己的二跳邻居，然后构筑二跳邻居存储的字典
                    key = (sender_ip, two_hop_ip)
                    if key not in self.two_hop_set:
                        print(f"[2-Hop] 发现: me -> {sender_ip} -> {two_hop_ip}")
                        self.two_hop_set[key] = TwoHopTuple(sender_ip, two_hop_ip)# 写入字典
                    
                    self.two_hop_set[key].expiration_time = current_time + validity_time

            # 规则 2: 如果对方说 NOT_NEIGH(0)，删除记录
            elif neigh_type == 0:
                for two_hop_ip in ip_list:
                    key = (sender_ip, two_hop_ip)
                    if key in self.two_hop_set:
                        print(f"[2-Hop] 链路断开: {sender_ip} -x-> {two_hop_ip}")
                        del self.two_hop_set[key]

    def cleanup(self):
        """清理过期记录"""
        now = time.time()
        # 清理 2跳
        keys_to_remove = [k for k, v in self.two_hop_set.items() if v.expiration_time < now]
        for k in keys_to_remove:
            del self.two_hop_set[k]
        # (可选) 这里也可以添加清理 neighbors 的逻辑，不过 neighbor 通常跟随 link 状态变化