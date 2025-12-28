#接收端简易代码

import socket

# 配置信息
# "0.0.0.0" 表示监听本机所有网络接口的 IP
LISTEN_IP = "0.0.0.0" 
LISTEN_PORT = 5005

# 1. 创建 UDP 套接字 (AF_INET 为 IPv4, SOCK_DGRAM 为 UDP)
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

# 2. 绑定 IP 和 端口
sock.bind((LISTEN_IP, LISTEN_PORT))

print(f"正在监听端口 {LISTEN_PORT}...")

try:
    while True:
        # 3. 接收数据 (缓冲区大小为 1024 字节)
        data, addr = sock.recvfrom(1024)
        print(f"来自 {addr} 的消息: {data.decode('utf-8')}")
except KeyboardInterrupt:
    print("\n接收停止。")
finally:
    sock.close()