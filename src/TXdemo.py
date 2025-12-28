#发送端UDP传输简易代码

import socket

# 配置信息
# 请将此处的 IP 替换为你已知的另一台主机的真实 IP
DEST_IP = "192.168.29.12" 
DEST_PORT = 5005
MESSAGE = "你好，这是一条来自 UDP 的消息！"

# 1. 创建 UDP 套接字
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

# 2. 发送数据
# 注意：UDP 发送的是字节流，所以字符串需要 encode()
try:
    sock.sendto(MESSAGE.encode('utf-8'), (DEST_IP, DEST_PORT))
    print(f"消息已发送至 {DEST_IP}:{DEST_PORT}")
finally:
    # 3. 关闭套接字
    sock.close()
