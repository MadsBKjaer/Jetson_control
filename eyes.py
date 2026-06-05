import zmq
import cv2
import numpy as np
import time

# 1. Setup ZeroMQ Request Socket (REQ)
context = zmq.Context()
socket = context.socket(zmq.REQ)
socket.connect("tcp://10.10.10.1:5555")

def get_vision(mode="FULL"):
    """mode can be 'FULL' or 'WINDOW'"""
    socket.send_string(mode)
    message = socket.recv()
    
    if message == b"NO_FRAME":
        return None
        
    np_arr = np.frombuffer(message, np.uint8)
    return cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

print("Connecting to Windows... Press 'q' in the window to quit.")

try:
    while True:
        # --- YOUR AI PIPELINE ---
        
        # The AI decides it needs to see the screen *right now*
        capture_start = time.perf_counter()
        frame = get_vision(mode="WINDOW")
        capture_end = time.perf_counter()
        
        if frame is not None:
            latency_ms = (capture_end - capture_start) * 1000
            print(f"Requested and received frame in {latency_ms:.1f} ms")
            
            cv2.imshow("Jetson AI View", frame)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
                
        # Simulate your AI model "thinking", running inference, or sending Bluetooth commands.
        # Notice that during this sleep time, NO frames are being sent over the network,
        # NO frames are being encoded, and the Jetson's CPU/GPU is entirely free.
        time.sleep(0.1)

except KeyboardInterrupt:
    print("Stopping AI...")
finally:
    cv2.destroyAllWindows()
    socket.close()
    context.term()