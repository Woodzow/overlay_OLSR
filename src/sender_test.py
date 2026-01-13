# src/sender_test.py
import socket
import time
import struct

# 导入你项目中的模块
from constants import *
from pkt_msg_fmt import create_packet_header, create_message_header, create_link_code
from hello_msg_body import create_hello_body

def run_sender_test(target_ip='<broadcast>', target_port=5005):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

    print(f"[*] [Sender] 准备向 {target_ip}:{target_port} 发送完整的 HELLO 测试包...")

    # --- 1. 模拟构建 HELLO 消息内容 (Hello Info) ---
    # 场景假设：
    # - 邻居组A: 对称邻居 (SYM_LINK, SYM_NEIGH) -> IP: 192.168.1.20, 192.168.1.21
    # - 邻居组B: 听到的邻居 (ASYM_LINK, NOT_NEIGH) -> IP: 192.168.1.55
    
    # 使用 pkt_msg_fmt 中的函数生成 Link Code
    code_sym = create_link_code(SYM_LINK, SYM_NEIGH)   # Code: 6
    code_asym = create_link_code(ASYM_LINK, NOT_NEIGH) # Code: 1 (假设 NOT_NEIGH=0, ASYM=1)

    # 构造 hello_info 字典
    hello_info = {
        "htime_seconds": 2.0,       # HELLO 间隔
        "willingness": WILL_DEFAULT, # 意愿值 3
        "neighbor_groups": [
            (code_sym, ["192.168.1.20", "192.168.1.21"]),
            (code_asym, ["192.168.1.55"])
        ]
    }

    # --- 2. 打包 HELLO Body ---
    try:
        hello_body_bytes = create_hello_body(hello_info)
        print(f"[Sender] HELLO Body 构建成功，长度: {len(hello_body_bytes)} bytes")
    except Exception as e:
        print(f"[Sender] HELLO Body 构建失败: {e}")
        return

    # --- 3. 打包 Message Header ---
    my_ip = "192.168.1.100"
    seq_num = 1
    
    msg_header = create_message_header(
        msg_type=msg_type["HELLO_MESSAGE"], # 1
        vtime_seconds=6.0,                  # 有效期
        msg_body_len=len(hello_body_bytes),
        originator_ip=my_ip,
        ttl=1,
        hop_count=0,
        msg_seq_num=seq_num
    )

    full_message = msg_header + hello_body_bytes

    # --- 4. 打包 Packet Header ---
    pkt_seq = 100
    pkt_header = create_packet_header(len(full_message), pkt_seq)

    # --- 5. 发送 ---
    final_data = pkt_header + full_message

    try:
        while True:
            sock.sendto(final_data, (target_ip, target_port))
            print(f"[Sender] 已发送数据包 (PacketSeq: {pkt_seq}, MsgSeq: {seq_num})")
            print(f"         包含邻居: 192.168.1.20, 192.168.1.21 (SYM), 192.168.1.55 (ASYM)")
            
            time.sleep(2) # 每2秒发一次
            pkt_seq += 1
            seq_num += 1
            # 重新打包头部以更新序列号 (可选，为了演示方便这里暂不更新body内部逻辑)
            pkt_header = create_packet_header(len(full_message), pkt_seq)
            final_data = pkt_header + full_message
            
    except KeyboardInterrupt:
        print("\n[Sender] 停止发送")
    finally:
        sock.close()

if __name__ == "__main__":
    # 如果你在本机测试，可以用 127.0.0.1 或者 <broadcast>
    # 确保防火墙允许 UDP 5005
    run_sender_test()