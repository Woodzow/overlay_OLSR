import time





class NeighborTuple:
    def __init__(self, main_addr):
        self.main_addr = main_addr
        self.status = 0         # 0: NOT_SYM, 1: SYM [cite: 504]
        self.willingness = 3    # 默认 WILL_DEFAULT [cite: 505]


class TwoHopTuple:
    def __init__(self, neighbor_main_addr, two_hop_addr):
        self.neighbor_main_addr = neighbor_main_addr  # 中间跳 (邻居) [cite: 509]
        self.two_hop_addr = two_hop_addr              # 目标 (邻居的邻居) [cite: 509]
        self.expiration_time = 0                      # 过期时间 [cite: 509]

def update_neighbor_status(self, neighbor_ip, link_status):
    """
    根据 LinkSet 的变化更新 Neighbor Set [cite: 882-887]
    """
    if neighbor_ip not in self.neighbors:
        self.neighbors[neighbor_ip] = NeighborTuple(neighbor_ip)
    
    neigh = self.neighbors[neighbor_ip]
    
    # 如果存在至少一个对称链路，则邻居状态为 SYM
    if link_status == "SYM":
        neigh.status = 1 # SYM
    else:
        neigh.status = 0 # NOT_SYM

class TopologyManager: # 或者继续在你的OLSR协议主类里
    def __init__(self, my_ip):
        self.my_ip = my_ip
        # 格式: { (neighbor_ip, two_hop_ip): TwoHopTuple }
        self.two_hop_set = {} 

    






