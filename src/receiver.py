import struct
import socket

def parse_packet(data, addr):
    """
    拆包逻辑：将收到的二进制 data 解析为可读信息
    """
    print(f"\n[+] 收到来自 {addr} 的数据，长度: {len(data)}")

    # --- 1. 解析 Packet Header (前4字节) ---
    # 格式: !HH (Length, SeqNum)
    if len(data) < 4:
        return # 数据太短，忽略 [cite: 293]
        
    pkt_len, pkt_seq = struct.unpack('!HH', data[:4])
    print(f"    Packet Header -> Length: {pkt_len}, Seq: {pkt_seq}")
    
    # 指针移动到 Packet Header 之后
    cursor = 4 
    
    # --- 2. 循环解析 Message (可能有多个) ---
    while cursor < len(data):
        # 确保剩余数据足够解析 Message Header (12字节)
        if len(data) - cursor < 12:
            break
            
        # 提取 12 字节的 Message Header
        # 格式: !BBH4sBBH
        msg_header_data = data[cursor : cursor+12]
        msg_type, vtime_byte, msg_size, orig_ip_bytes, ttl, hop, msg_seq = \
            struct.unpack('!BBH4sBBH', msg_header_data)
            
        # 将 IP 的二进制转回字符串 "192.168.x.x"
        orig_ip_str = socket.inet_ntoa(orig_ip_bytes)
        
        print(f"    [Message Found] Type: {msg_type} (HELLO), Originator: {orig_ip_str}")
        print(f"    Size: {msg_size}, TTL: {ttl}, Seq: {msg_seq}")
        
        # --- 3. 提取 Message Body ---
        # Body 的长度 = 整个消息长度 - 头部长度(12)
        body_len = msg_size - 12
        if body_len > 0:
            # 这里的 body 就是具体的 HELLO 内容 (Link Code 等)
            # 目前我们还没有解析它，先提取出来
            body_data = data[cursor+12 : cursor+msg_size]
            # TODO: 将来这里会调用 parse_hello_body(body_data)
        
        # 指针移动到下一条消息的开头
        cursor += msg_size

def start_receiver(listen_port=5005):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(('0.0.0.0', listen_port))
    print(f"[*] 监听端口 {listen_port} 等待 OLSR 数据包...")
    
    while True:
        data, addr = sock.recvfrom(1024) # 缓冲区设大一点
        parse_packet(data, addr)