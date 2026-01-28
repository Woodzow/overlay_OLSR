#本文件主要是将可播放的视频格式转化为可以进行发送的一个一个的数据包
import socket
import time
import os
import sys

def send_video_udp(file_path, dest_ip, dest_port):
    # 创建 UDP Socket
    # AF_INET = IPv4, SOCK_DGRAM = UDP
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    
    # 检查文件是否存在
    if not os.path.exists(file_path):
        print(f"错误: 文件 {file_path} 不存在")
        return

    file_size = os.path.getsize(file_path)
    print(f"开始发送文件: {file_path} ({file_size / 1024 / 1024:.2f} MB)")                                                                         
    print(f"目标: {dest_ip}:{dest_port}")

    # 定义缓冲区大小 (Buffer Size)
    # 注意：如果经过公网路由器，MTU 通常限制在 1472 字节左右。
    # 局域网内可以使用较大的包，这里设为 60KB (61440 bytes)
    BUFFER_SIZE = 61440 
    
    sent_bytes = 0
    
    try:
        with open(file_path, "rb") as f:
            while True:
                # 读取数据块
                data = f.read(BUFFER_SIZE)
                
                # 如果读不到数据，说明文件结束
                if not data:
                    break
                
                # 发送数据
                sock.sendto(data, (dest_ip, dest_port))
                sent_bytes += len(data)
                
                # --- 简单的流控 ---
                # 如果发送太快，接收端可能来不及处理导致丢包
                # 根据网络情况调整 sleep 时间，或者移除
                time.sleep(0.002) 
                
                # 打印进度 (可选)
                sys.stdout.write(f"\r已发送: {sent_bytes / file_size * 100:.2f}%")
                sys.stdout.flush()

        # 发送结束标记
        # 我们发送一个特殊的空包或特定字符串作为结束信号
        print("\n发送结束信号...")
        sock.sendto(b'EOF_MARKER', (dest_ip, dest_port))
        
        print("传输完成。")

    except Exception as e:
        print(f"\n发生错误: {e}")
    finally:
        sock.close()


import socket

def receive_video_udp(save_path, listen_port):
    # 创建 UDP Socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    
    # 绑定端口 (0.0.0.0 表示接收所有网卡的流量)
    sock.bind(("0.0.0.0", listen_port))
    print(f"正在监听端口 {listen_port}，等待数据...")
    
    # 设置缓冲区，必须大于或等于发送端的包大小
    BUFFER_SIZE = 65535 

    try:
        with open(save_path, "wb") as f:
            while True:
                # 接收数据
                data, addr = sock.recvfrom(BUFFER_SIZE)
                
                # 检查是否是结束标记
                if data == b'EOF_MARKER':
                    print(f"\n收到来自 {addr} 的结束信号。")
                    break
                
                # 将数据写入文件
                f.write(data)
                
    except KeyboardInterrupt:
        print("\n手动停止接收。")
    except Exception as e:
        print(f"发生错误: {e}")
    finally:
        sock.close()
        print(f"文件已保存至: {save_path}")