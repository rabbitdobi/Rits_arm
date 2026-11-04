import cv2
import mediapipe as mp
import math
from pathlib import Path

# --- Configurations ---
WINDOW_NAME = "uHand UNO - Right Hand Tracker"
MODEL_PATH = Path("hand_landmarker.task")

BaseOptions = mp.tasks.BaseOptions
HandLandmarker = mp.tasks.vision.HandLandmarker
HandLandmarkerOptions = mp.tasks.vision.HandLandmarkerOptions
RunningMode = mp.tasks.vision.RunningMode

# Finger tips, intermediate joints, knuckle joints, and bases indices (based on MediaPipe specifications)
FINGER_JOINTS = {
    "Thumb":  (4, 3, 2, 1),
    "Index":  (8, 7, 6, 5),
    "Middle": (12, 11, 10, 9),
    "Ring":   (16, 15, 14, 13),
    "Pinky":  (20, 19, 18, 17)
}

def calculate_finger_bend(landmarks, finger_indices):
    tip_idx, _, _, base_idx = finger_indices
    tip = landmarks[tip_idx]
    base = landmarks[base_idx]
    wrist = landmarks[0]
    
    # Calculate distance from fingertip to wrist
    distance = math.sqrt((tip.x - wrist.x)**2 + (tip.y - wrist.y)**2 + (tip.z - wrist.z)**2)
    return distance

def main():
    if not MODEL_PATH.exists():
        raise SystemExit(f"Model file not found: {MODEL_PATH}\nPlease run the download command.")

    # Initialize MediaPipe HandLandmarker for up to 2 hands
    options = HandLandmarkerOptions(
        base_options=BaseOptions(model_asset_path=str(MODEL_PATH)),
        running_mode=RunningMode.IMAGE,
        num_hands=2
    )
    detector = HandLandmarker.create_from_options(options)

    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        raise SystemExit("Could not open camera.")

    print("uHand right-hand tracker started. Press 'q' to exit.")

    try:
        while cap.isOpened():
            success, frame = cap.read()
            if not success:
                break

            # 1. Detect on raw frame
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
            result = detector.detect(mp_image)

            # 2. Flip horizontally for mirror display
            display = cv2.flip(frame, 1)

            finger_status = {}
            target_found = False

            if result.hand_landmarks:
                for idx, landmarks in enumerate(result.hand_landmarks):
                    # Use the wrist (landmark 0) x-coordinate on the mirrored display (1 - lm.x)
                    # On a built-in selfie camera, your right hand appears on the right side of the screen (x > 0.5)
                    wrist_x = 1.0 - landmarks[0].x

                    if wrist_x > 0.5:  # Right side of the mirror display
                        target_found = True
                        h, w, _ = display.shape

                        # Draw 21 joint landmarks on screen with proper coordinates
                        for lm in landmarks:
                            cx = int((1.0 - lm.x) * w)
                            cy = int(lm.y * h)
                            cv2.circle(display, (cx, cy), 4, (0, 255, 0), -1)

                        # Calculate bend for each of the 5 fingers
                        for name, indices in FINGER_JOINTS.items():
                            val = calculate_finger_bend(landmarks, indices)
                            finger_status[name] = round(val, 2)
                        
                        break # Track only the target hand

            # Display status on screen
            y_offset = 50
            if target_found:
                cv2.putText(display, "Target: RIGHT HAND", (30, y_offset), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                y_offset += 30
                for name, val in finger_status.items():
                    text = f"{name}: {val}"
                    cv2.putText(display, text, (30, y_offset), 
                                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
                    y_offset += 30
            else:
                cv2.putText(display, "Please show your RIGHT hand (Right side)", (30, y_offset), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)

            cv2.imshow(WINDOW_NAME, display)

            # Exit on 'q' key
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

    finally:
        detector.close()
        cap.release()
        cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
