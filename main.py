import cv2
import mediapipe as mp
import math
from pathlib import Path

# --- Configurations ---
WINDOW_NAME = "uHand UNO - Finger Tracker"
MODEL_PATH = Path("hand_landmarker.task") # Model file downloaded previously

BaseOptions = mp.tasks.BaseOptions
HandLandmarker = mp.tasks.vision.HandLandmarker
HandLandmarkerOptions = mp.tasks.vision.HandLandmarkerOptions
RunningMode = mp.tasks.vision.RunningMode

# Finger tips, intermediate joints, knuckle joints, and bases indices (based on MediaPipe specifications)
# (Tip, Intermediate, Joint, Base)
FINGER_JOINTS = {
    "Thumb":  (4, 3, 2, 1),
    "Index":  (8, 7, 6, 5),
    "Middle": (12, 11, 10, 9),
    "Ring":   (16, 15, 14, 13),
    "Pinky":  (20, 19, 18, 17)
}

def calculate_finger_bend(landmarks, finger_indices):
    """
    Function to roughly calculate finger bend (applicable to distance from wrist or joint angles).
    This example uses the distance between the fingertip and wrist (index 0) to determine if a finger is closed or open.
    """
    tip_idx, _, _, base_idx = finger_indices
    tip = landmarks[tip_idx]
    base = landmarks[base_idx]
    wrist = landmarks[0]
    
    # Calculate distance from fingertip to wrist (longer when extended, shorter when bent)
    distance = math.sqrt((tip.x - wrist.x)**2 + (tip.y - wrist.y)**2 + (tip.z - wrist.z)**2)
    return distance

def main():
    if not MODEL_PATH.exists():
        raise SystemExit(f"Model file not found: {MODEL_PATH}\nPlease run the download command.")

    # Initialize MediaPipe HandLandmarker
    options = HandLandmarkerOptions(
        base_options=BaseOptions(model_asset_path=str(MODEL_PATH)),
        running_mode=RunningMode.IMAGE, # Real-time image processing mode first
        num_hands=1 # Single hand
    )
    detector = HandLandmarker.create_from_options(options)

    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        raise SystemExit("Could not open camera.")

    print("uHand finger tracker started. Press 'q' to exit.")

    try:
        while cap.isOpened():
            success, frame = cap.read()
            if not success:
                break

            # Horizontal flip (mirror view)
            display = cv2.flip(frame, 1)
            
            # Convert to RGB image for MediaPipe
            rgb = cv2.cvtColor(display, cv2.COLOR_BGR2RGB)
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)

            # Detect hands
            result = detector.detect(mp_image)

            finger_status = {}

            if result.hand_landmarks:
                landmarks = result.hand_landmarks[0]
                h, w, _ = display.shape

                # Draw 21 joint landmarks on screen
                for lm in landmarks:
                    cx, cy = int(lm.x * w), int(lm.y * h)
                    cv2.circle(display, (cx, cy), 4, (0, 255, 0), -1)

                # Calculate bend for each of the 5 fingers
                for name, indices in FINGER_JOINTS.items():
                    val = calculate_finger_bend(landmarks, indices)
                    finger_status[name] = round(val, 2)

            # Display each finger status (values) on screen
            y_offset = 50
            for name, val in finger_status.items():
                text = f"{name}: {val}"
                cv2.putText(display, text, (30, y_offset), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
                y_offset += 30

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