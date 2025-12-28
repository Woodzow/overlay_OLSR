from constants import *
import time
import socket
from pkt_msg_fmt import create_packet_header, create_message_header, encode_mantissa
# 引入你刚才写好的打包函数
# from olsr_packet import create_packet_header, create_message_header, encode_mantissa

def start_sender(target_ip='<broadcast>', target_port=5005):
    # 创建 UDP Socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    
    # 允许发送广播 (如果你用单播IP，这行可以不加，但加上也没坏处)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

    print(f"[*] 开始向 {target_ip}:{target_port} 发送 HELLO 消息...")
    
    seq_num = 0
    while True:
        # 1. 准备数据 (模拟空的 HELLO Body)
        # 这里的 body 暂时还是空的，以后我们要在这里填入邻居列表
        # Reserved(2字节) + Htime(1字节, 2秒) + Willingness(1字节, 默认3)
        hello_body = b'\x00\x00' + bytes([encode_mantissa(2.0)]) + b'\x03'
        
        # 2. 封装 Message Header (Type 1 = HELLO)
        msg_header = create_message_header(
            msg_type=1, vtime_seconds=6.0, msg_body_len=len(hello_body),
            originator_ip="192.168.1.100", # 替换为你虚拟机的真实IP
            ttl=1, hop_count=0, msg_seq_num=seq_num
        )
        
        # 3. 封装 Packet Header
        pkt_header = create_packet_header(len(msg_header) + len(hello_body), seq_num)
        
        # 4. 拼接并通过 UDP 发送
        data = pkt_header + msg_header + hello_body
        sock.sendto(data, (target_ip, target_port))
        
        print(f"Sent Packet #{seq_num} ({len(data)} bytes)")
        
        seq_num += 1
        time.sleep(HELLO_INTERVAL) # HELLO_INTERVAL