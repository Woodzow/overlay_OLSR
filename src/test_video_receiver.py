import socket
import struct
import time
import cv2
import numpy as np

HEADER_FMT = "!IHH"
HEADER_SIZE = struct.calcsize(HEADER_FMT)

def main():
    bind_ip = "0.0.0.0"
    bind_port = 5000
    recv_buf = 4 * 1024 * 1024

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, recv_buf)
    sock.bind((bind_ip, bind_port))

    print(f"Listening on udp://{bind_ip}:{bind_port}")

    current_frame_id = None
    chunks = {}
    expected_total = 0
    last_update = time.time()
    frame_timeout_sec = 0.2  # 一帧收不齐就丢，避免卡死

    while True:
        pkt, _ = sock.recvfrom(65535)
        if len(pkt) < HEADER_SIZE:
            continue

        frame_id, chunk_id, total_chunks = struct.unpack(HEADER_FMT, pkt[:HEADER_SIZE])
        payload = pkt[HEADER_SIZE:]
        now = time.time()

        if current_frame_id is None or frame_id != current_frame_id:
            current_frame_id = frame_id
            chunks = {}
            expected_total = total_chunks

        if chunk_id < total_chunks:
            chunks[chunk_id] = payload
            last_update = now
            expected_total = total_chunks

        if expected_total > 0 and len(chunks) == expected_total:
            data = b"".join(chunks[i] for i in range(expected_total) if i in chunks)
            arr = np.frombuffer(data, dtype=np.uint8)
            img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
            if img is not None:
                cv2.imshow("UDP Video", img)
            chunks = {}
            expected_total = 0

        if expected_total > 0 and (now - last_update) > frame_timeout_sec:
            chunks = {}
            expected_total = 0

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cv2.destroyAllWindows()
    sock.close()

if __name__ == "__main__":
    main()
