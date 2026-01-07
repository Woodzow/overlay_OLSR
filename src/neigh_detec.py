import time


from constants import WILL_NEVER
from mpr_selector import select_mpr


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

    # 下面获取一些要来进行MPR选择算法计算的数据内容：一跳对称邻居有哪些。二跳有哪些。需要注意只有对称的邻居才能够进行收发，才能够选作MPR节点
    def get_symmetric_neighbors(self):
        """获取所有对称 1跳邻居 (集合 N ),这里获取的是NeighborTuple类的对象,也就是存储邻居相关信息的类"""
        return [ip for ip, neigh in self.neighbors.items() if neigh.status == 1]

    def get_strict_2hop_neighbors(self):
        """
        获取所有严格 2 跳邻居 (集合 N2 )
        定义: 所有的在 2 跳表中的,但不是我自己,也不是我的对称 1 跳邻居
        """
        sym_neighbors = set(self.get_symmetric_neighbors())
        strict_2hop = set()
        
        # 遍历所有 2跳记录
        for (neighbor_ip, two_hop_ip), tuple_obj in self.two_hop_set.items():
            # 确保中间跳(neighbor_ip)是对称邻居 (RFC要求通过对称邻居到达)
            if neighbor_ip in sym_neighbors:
                # 排除我自己和我的直连邻居，其余的添加到二跳邻居集合中
                if two_hop_ip != self.my_ip and two_hop_ip not in sym_neighbors:
                    strict_2hop.add(two_hop_ip)
        
        return strict_2hop

    def get_reachability_map(self):
        """
        构建覆盖关系映射
        返回的是一个字典，格式为: { neighbor_ip: {covered_2hop_ip1, covered_2hop_ip2, ...} }
        """
        sym_neighbors = self.get_symmetric_neighbors()
        strict_2hop = self.get_strict_2hop_neighbors()
        
        #这是一个字典推导式：这里遍历 sym_neighbors，对每个 neigh 生成一项：neigh 作为键，set() 作为值。
        reachability = {neigh: set() for neigh in sym_neighbors}
        
        # 在二跳邻居（不严格）对象里面的选出是一跳对称，而且二跳为严格二跳的构成集合
        for (neighbor_ip, two_hop_ip) in self.two_hop_set:
            if neighbor_ip in reachability and two_hop_ip in strict_2hop:
                reachability[neighbor_ip].add(two_hop_ip)
                
        return reachability
    

    def recalculate_mpr(self):
        """
        准备数据并调用算法
        """
        print("[MPR] 开始重算 MPR...")
        
        # 1. 准备 candidates 字典 {ip: willingness}
        # 直接在这里遍历，替代了原先的冗余的 _get_symmetric_neighbors_data
        candidates = {
            ip: neigh.willingness 
            for ip, neigh in self.neighbors.items() 
            if neigh.status == 1
        }
        
        # 2. 准备 coverage_map 字典 {neighbor_ip: set(strict_2hop_ips)}
        # 直接在这里构建，替代了 _get_coverage_map 和 get_reachability_map
        coverage_map = {ip: set() for ip in candidates}
        
        # 先获取严格2跳集合，避免重复判断
        strict_2hop_targets = self.get_strict_2hop_neighbors()
        
        # 遍历二跳表，填充覆盖关系
        for (neighbor_ip, two_hop_ip) in self.two_hop_set:
            # 如果 中间人是候选人 AND 目标是严格2跳
            if neighbor_ip in coverage_map and two_hop_ip in strict_2hop_targets:
                coverage_map[neighbor_ip].add(two_hop_ip)
        
        # 3. 调用独立算法模块
        new_mpr_set = select_mpr(candidates, coverage_map)
        
        if new_mpr_set != self.current_mpr_set:
            print(f"[MPR] MPR集合更新: {self.current_mpr_set} -> {new_mpr_set}")
            self.current_mpr_set = new_mpr_set
        else:
            print(f"[MPR] MPR集合未变: {self.current_mpr_set}")
            
        return self.current_mpr_set