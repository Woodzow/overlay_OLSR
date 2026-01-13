# src/receiver_test.py
import socket
import struct
import time

# 导入你项目中的模块
from constants import *
from hello_msg_body import parse_hello_body

def parse_full_packet(data, addr):
    """
    完整解析流程：Packet -> Message -> Hello Body
    """
    print(f"\n{'='*50}")
    print(f"[Receiver] 收到来自 {addr} 的数据，总长: {len(data)} bytes")

    # 1. 解析 Packet Header
    if len(data) < 4:
        print("Error: 数据包太短")
        return
    pkt_len, pkt_seq = struct.unpack('!HH', data[:4])
    print(f"[Packet Header] Length={pkt_len}, Seq={pkt_seq}")

    cursor = 4
    
    # 2. 遍历 Message
    while cursor < len(data):
        # 检查剩余长度是否足够读取 Message Header (12 bytes)
        remaining = len(data) - cursor
        if remaining < 12:
            break
            
        # 提取 Message Header
        msg_header_data = data[cursor : cursor+12]
        m_type, vtime_byte, m_size, orig_ip_bytes, ttl, hop, m_seq = struct.unpack('!BBH4sBBH', msg_header_data)
        
        orig_ip_str = socket.inet_ntoa(orig_ip_bytes)
        
        print(f"  --> [Message Header]")
        print(f"      Type: {m_type} ({'HELLO' if m_type==1 else 'UNKNOWN'})")
        print(f"      Originator: {orig_ip_str}, Seq: {m_seq}, Size: {m_size}")
        
        # 3. 提取 Message Body 并解析
        # Body 长度 = Message Size - 12
        body_len = m_size - 12
        
        # 确保数据足够
        if len(data) - (cursor + 12) < body_len:
            print("      Error: 消息体数据不完整")
            break
            
        body_data = data[cursor+12 : cursor+m_size]
        
        # === 关键步骤：调用你的 hello_msg_body.py 进行解析 ===
        if m_type == msg_type["HELLO_MESSAGE"]:
            print(f"      [Parsing HELLO Body...]")
            hello_info = parse_hello_body(body_data)
            
            if hello_info:
                print(f"      Htime: {hello_info['htime_seconds']}s")
                print(f"      Willingness: {hello_info['willingness']}")
                
                groups = hello_info.get('neighbor_groups', [])
                print(f"      Neighbor Groups ({len(groups)} groups):")
                
                for idx, (link_code, ip_list) in enumerate(groups):
                    # 解析 Link Code (参考 pkt_msg_fmt.py)
                    # Link Type (Bit 0-1), Neighbor Type (Bit 2-3)
                    l_type = link_code & 0x03
                    n_type = (link_code >> 2) & 0x03
                    
                    type_str = f"LinkType={l_type}, NeighType={n_type}"
                    print(f"        Group {idx+1}: Code=0x{link_code:02x} ({type_str})")
                    print(f"          IPs: {ip_list}")
            else:
                print("      Error: HELLO Body 解析失败")
        else:
            print(f"      (暂未实现类型 {m_type} 的解析)")
            
        # 移动指针到下一条消息
        cursor += m_size

def run_receiver_test(listen_port=5005):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    # 绑定到所有接口
    sock.bind(('0.0.0.0', listen_port))
    
    print(f"[*] [Receiver] 正在监听端口 {listen_port} ...")
    
    try:
        while True:
            data, addr = sock.recvfrom(2048)
            parse_full_packet(data, addr)
    except KeyboardInterrupt:
        print("\n[Receiver] 停止监听")
    finally:
        sock.close()

if __name__ == "__main__":
    run_receiver_test()