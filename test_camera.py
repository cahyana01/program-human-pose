import cv2
import time

def test_camera():
    print("Attempting to open camera (index 0)...")
    cap = cv2.VideoCapture(0)
    
    if not cap.isOpened():
        print("Error: Could not open camera (index 0).")
        # Try index 1 just in case
        print("Attempting to open camera (index 1)...")
        cap = cv2.VideoCapture(1)
        if not cap.isOpened():
             print("Error: Could not open camera (index 1) either.")
             return

    print("Camera opened successfully.")
    
    # Try reading a few frames
    for i in range(5):
        ret, frame = cap.read()
        if not ret:
            print(f"Error: Failed to read frame {i+1}")
        else:
            print(f"Frame {i+1} read successfully. Size: {frame.shape}")
        time.sleep(0.5)
        
    cap.release()
    print("Camera released.")

if __name__ == "__main__":
    test_camera()
