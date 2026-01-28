import socket
import struct
import time
import cv2

HEADER_FMT = "!IHH"
HEADER_SIZE = struct.calcsize(HEADER_FMT)

def main():
    # === 配置 ===
    video_path = "demo.mp4"   # 改成你要发送的视频文件
    dst_ip = "192.168.3.10"       # 改成接收端IP
    dst_port = 5000

    max_payload = 1200         # UDP负载大小（不含头）
    jpeg_quality = 60          # JPEG质量(0-100)
    realtime = True            # True: 按视频原FPS节奏发送；False: 尽快发送

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 4 * 1024 * 1024)

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise RuntimeError(f"无法打开视频文件: {video_path}")

    fps = cap.get(cv2.CAP_PROP_FPS)
    if fps is None or fps <= 1e-6:
        fps = 25.0
    frame_interval = 1.0 / fps

    encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), int(jpeg_quality)]
    frame_id = 0

    print(f"Sending file '{video_path}' to udp://{dst_ip}:{dst_port}, fps={fps:.2f}")

    last_send = time.time()

    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                print("视频读取结束。")
                break

            # 可选：缩小分辨率降码率
            # frame = cv2.resize(frame, (640, 360))

            ok, buf = cv2.imencode(".jpg", frame, encode_param)
            if not ok:
                continue
            data = buf.tobytes()

            total_chunks = (len(data) + max_payload - 1) // max_payload

            for chunk_id in range(total_chunks):
                start = chunk_id * max_payload
                end = min(start + max_payload, len(data))
                payload = data[start:end]
                header = struct.pack(HEADER_FMT, frame_id, chunk_id, total_chunks)
                sock.sendto(header + payload, (dst_ip, dst_port))

            frame_id = (frame_id + 1) & 0xFFFFFFFF

            # 按原FPS节奏发送（可选）
            if realtime:
                now = time.time()
                elapsed = now - last_send
                sleep_time = frame_interval - elapsed
                if sleep_time > 0:
                    time.sleep(sleep_time)
                last_send = time.time()

    except KeyboardInterrupt:
        print("Sender stopped.")
    finally:
        cap.release()
        sock.close()

if __name__ == "__main__":
    main()
