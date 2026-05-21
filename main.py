import cv2
import mediapipe as mp
import pyautogui
import time
import math
import numpy as np

from ctypes import cast, POINTER
from comtypes import CLSCTX_ALL
from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
import screen_brightness_control as sbc




import threading

shared_result = None
shared_frame = None
lock = threading.Lock()
running = True



# ===================== PYAutoGUI =====================
pyautogui.FAILSAFE = False
screen_w, screen_h = pyautogui.size()

# ===================== VOLUME SETUP =====================
devices = AudioUtilities.GetSpeakers()
interface = devices.Activate(
    IAudioEndpointVolume._iid_,
    CLSCTX_ALL,
    None
)
volume = cast(interface, POINTER(IAudioEndpointVolume))

MIN_VOL, MAX_VOL = volume.GetVolumeRange()[:2]
prev_left_angle = None
VOLUME_SENSITIVITY = 25
ANGLE_DEADZONE = 0.01

# ===================== BRIGHTNESS SETUP =====================
prev_index_y = None
BRIGHTNESS_SENSITIVITY = 200  # Adjust for faster/slower brightness control
BRIGHTNESS_DEADZONE = 0.01

# ===================== MEDIAPIPE =====================
mp_hands = mp.solutions.hands
hands = mp_hands.Hands(
    max_num_hands=2,
    min_detection_confidence=0.7,
    min_tracking_confidence= 0.7
)
mp_draw = mp.solutions.drawing_utils

# ===================== CAMERA =====================
cap = cv2.VideoCapture(0)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

# ===================== CURSOR SETTINGS (FROM ORIGINAL) =====================
# ===================== CURSOR SETTINGS (FROM ORIGINAL) =====================
smooth_factor = 0.3
prev_x, prev_y = 0, 0
SENSITIVITY_MULTIPLIER = 2

PINCH_THRESHOLD = 30
RELEASE_THRESHOLD = 45
HOLD_TIME = 0.4  # Increased from 0.3
mouse_down = False
pinch_start_time = None
was_pinching = False

# Double-click settings - IMPROVED
last_click_time = 0
DOUBLE_CLICK_TIME = 0.9  # More lenient timing
click_count = 0  # NEW - Track number of clicks
last_click_completed_time = 0  # NEW
CLICK_RESET_TIME = 1.1  # NEW - Time to reset click counter
click_cooldown = 0  # ADD THIS LINE - Initialize cooldown
COOLDOWN_TIME = 0.1  # Reduced from 0.2

DEAD_ZONE_X = 0.02
DEAD_ZONE_Y = 0.02
prev_time = 0
fps = 0

# ===================== SCROLL SETTINGS (ADD TO GLOBAL VARIABLES) =====================
prev_right_index_y = None
prev_right_middle_y = None
SCROLL_SENSITIVITY = 5000  # Adjust for faster/slower scrolling (higher = faster)
SCROLL_DEADZONE = 0.01   # Minimum movement to trigger scroll

# ===================== FUNCTIONS =====================





def check_scroll_gesture(landmarks):
    """
    Check if scroll gesture is active
    Returns True only when index and middle fingers are extended, all others closed (including thumb)
    """
    # Check finger states
    thumb_closed = landmarks[4].x < landmarks[3].x  # Thumb tucked in
    index_closed = is_finger_closed(landmarks, 8, 6)      # Index - should be OPEN
    middle_closed = is_finger_closed(landmarks, 12, 10)   # Middle - should be OPEN
    ring_closed = is_finger_closed(landmarks, 16, 14)     # Ring - should be CLOSED
    pinky_closed = is_finger_closed(landmarks, 20, 18)    # Pinky - should be CLOSED
    
    # Scroll gesture active ONLY when:
    # - Index and Middle are OPEN
    # - Thumb, Ring, and Pinky are CLOSED
    return not index_closed and not middle_closed and thumb_closed and ring_closed and pinky_closed




def camera_worker():
    global shared_result, shared_frame, running

    cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)  # IMPORTANT
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    while running:
        success, frame = cap.read()
        if not success:
            continue

        frame = cv2.flip(frame, 1)
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        result = hands.process(rgb)

        with lock:
            shared_frame = frame
            shared_result = result

    cap.release()










def smooth_coordinates(current_x, current_y, prev_x, prev_y, factor):
    """Apply exponential smoothing to cursor movement"""
    smooth_x = prev_x + (current_x - prev_x) * factor
    smooth_y = prev_y + (current_y - prev_y) * factor
    return smooth_x, smooth_y

def map_to_screen(x, y, dead_zone_x, dead_zone_y, sensitivity=1.0):
    """Map hand coordinates to screen with dead zones and sensitivity multiplier"""
    # Center the coordinates around 0.5
    x_centered = x - 0.5
    y_centered = y - 0.5
    
    # Apply sensitivity multiplier
    x_centered *= sensitivity
    y_centered *= sensitivity
    
    # Re-center back to 0-1 range
    x = x_centered + 0.5
    y = y_centered + 0.5
    
    # Apply dead zones
    x = (x - dead_zone_x) / (1 - 2 * dead_zone_x)
    y = (y - dead_zone_y) / (1 - 2 * dead_zone_y)
    
    # Clamp to valid range
    x = max(0, min(1, x))
    y = max(0, min(1, y))
    
    return x * screen_w, y * screen_h

def is_finger_closed(landmarks, finger_tip_id, finger_pip_id):
    """Check if a finger is closed/curled by comparing tip and PIP joint positions"""
    tip = landmarks[finger_tip_id]
    pip = landmarks[finger_pip_id]
    
    # For most fingers, if tip y-coordinate is greater than PIP, finger is curled
    # (y increases downward in image coordinates)
    return tip.y > pip.y

def check_cursor_gesture(landmarks):
    """
    Check if cursor should be active based on hand gesture
    Returns True if hand is OPEN (all fingers extended)
    Returns False if hand is CLOSED (3+ fingers closed)
    """
    # Check each finger (excluding thumb)
    middle_closed = is_finger_closed(landmarks, 12, 10)  # Middle finger
    ring_closed = is_finger_closed(landmarks, 16, 14)    # Ring finger
    pinky_closed = is_finger_closed(landmarks, 20, 18)   # Pinky finger
    index_closed = is_finger_closed(landmarks, 8, 6)     # Index finger
    
    # Count how many fingers are closed
    closed_count = sum([index_closed, middle_closed, ring_closed, pinky_closed])
    
    # Cursor active when hand is OPEN (2 or fewer fingers closed)
    # Cursor stops when hand is CLOSED (3 or more fingers closed)
    return closed_count <= 2

def hand_angle(wrist, finger):
    """Calculate angle of hand rotation for volume control"""
    dx = finger.x - wrist.x
    dy = wrist.y - finger.y
    return math.atan2(dy, dx)

def check_volume_gesture(landmarks):
    """
    Check if volume control gesture is active
    Returns True only when middle and ring fingers are closed, others extended
    """
    # Check finger states
    index_closed = is_finger_closed(landmarks, 8, 6)      # Index - should be OPEN
    middle_closed = is_finger_closed(landmarks, 12, 10)   # Middle - should be CLOSED
    ring_closed = is_finger_closed(landmarks, 16, 14)     # Ring - should be CLOSED
    pinky_closed = is_finger_closed(landmarks, 20, 18)    # Pinky - should be OPEN
    
    # Volume control active ONLY when:
    # - Middle and Ring are CLOSED
    # - Index and Pinky are OPEN
    return middle_closed and ring_closed and not index_closed and not pinky_closed

def check_brightness_gesture(landmarks):
    """
    Check if brightness control gesture is active
    Returns True only when index finger is extended, all others closed
    """
    # Check finger states
    index_closed = is_finger_closed(landmarks, 8, 6)      # Index - should be OPEN
    middle_closed = is_finger_closed(landmarks, 12, 10)   # Middle - should be CLOSED
    ring_closed = is_finger_closed(landmarks, 16, 14)     # Ring - should be CLOSED
    pinky_closed = is_finger_closed(landmarks, 20, 18)    # Pinky - should be CLOSED
    
    # Brightness control active ONLY when:
    # - Index is OPEN
    # - Middle, Ring, and Pinky are CLOSED
    return not index_closed and middle_closed and ring_closed and pinky_closed

# ===================== MAIN LOOP =====================


print("RIGHT HAND Controls:")
print("  SCROLL MODE (Orange):")
print("    • Extend index + middle fingers (close thumb, ring, pinky)")
print("    • Move 2 fingers UP → Scroll UP")
print("    • Move 2 fingers DOWN → Scroll DOWN")
print("")
print("  CURSOR MODE:")
print("    • Open hand → Cursor moves")
print("    • Closed fist → Cursor stops")
print("    • Pinch (thumb + index) briefly → Click")
print("    • Pinch twice quickly → Double-click")
print("    • Hold pinch → Drag")

print("=" * 60)
print("Hand Mouse + Volume + Brightness Control")
print("=" * 60)
print("LEFT HAND Controls:")
print("  VOLUME (Green):")
print("    • Close ONLY middle + ring fingers (keep index & pinky extended)")
print("    • Rotate hand clockwise/counter-clockwise → Volume Up/Down")
print("")
print("  BRIGHTNESS (Orange):")
print("    • Extend ONLY index finger (close all others)")
print("    • Move finger UP → Brightness Up")
print("    • Move finger DOWN → Brightness Down")
print("")
print("RIGHT HAND Controls:")
print("  • Open hand → Cursor moves")
print("  • Closed fist → Cursor stops")
print("  • Pinch (thumb + index) briefly → Click")
print("  • Pinch twice quickly → Double-click")
print("  • Hold pinch → Drag")
print("")
print("Press ESC to exit")
print("=" * 60)
print()







threading.Thread(target=camera_worker, daemon=True).start()







while True:
    with lock:
      frame = shared_frame
      result = shared_result

    if frame is None or result is None:
      continue

    h, w, _ = frame.shape

    # Calculate FPS
    current_time = time.time()
    
    
    dt = current_time - prev_time
    if dt <= 0:
        dt = 1e-6  # prevent division by zero

    fps = 1 / dt
    prev_time = current_time

    prev_time = current_time

    # Track if left hand was detected this frame
    left_hand_detected = False

    if result.multi_hand_landmarks:
        for i, hand in enumerate(result.multi_hand_landmarks):
            hand_label = result.multi_handedness[i].classification[0].label
            lm = hand.landmark

            # ===================== LEFT HAND → VOLUME & BRIGHTNESS CONTROL =====================
            if hand_label == "Left":
                left_hand_detected = True
                
                # Check which gesture is active
                volume_gesture_active = check_volume_gesture(lm)
                brightness_gesture_active = check_brightness_gesture(lm)
                
                # ========== VOLUME CONTROL ==========
                if volume_gesture_active:
                    wrist = lm[0]
                    index_tip = lm[8]

                    # Calculate hand rotation angle
                    angle = hand_angle(wrist, index_tip)

                    # Control volume based on angle change
                    if prev_left_angle is not None:
                        delta = angle - prev_left_angle
                        # Handle angle wraparound
                        if abs(delta) > math.pi:
                            delta = 0

                        # Apply volume change if rotation detected
                        if abs(delta) > ANGLE_DEADZONE:
                            current_vol = volume.GetMasterVolumeLevel()
                            new_vol = current_vol - delta * VOLUME_SENSITIVITY
                            new_vol = max(MIN_VOL, min(MAX_VOL, new_vol))
                            volume.SetMasterVolumeLevel(new_vol, None)

                    # Always update the previous angle when gesture is active
                    prev_left_angle = angle
                else:
                    # Reset angle when gesture is not active
                    prev_left_angle = None
                
                # ========== BRIGHTNESS CONTROL ==========
                if brightness_gesture_active:
                    index_tip = lm[8]
                    current_index_y = index_tip.y  # Y coordinate (0 at top, 1 at bottom)
                    
                    # Control brightness based on vertical movement
                    if prev_index_y is not None:
                        delta_y = current_index_y - prev_index_y
                        
                        # Apply brightness change if movement detected
                        if abs(delta_y) > BRIGHTNESS_DEADZONE:
                            try:
                                current_brightness = sbc.get_brightness()[0]
                                # Move finger UP (decrease y) = increase brightness
                                # Move finger DOWN (increase y) = decrease brightness
                                new_brightness = current_brightness - (delta_y * BRIGHTNESS_SENSITIVITY)
                                new_brightness = max(0, min(100, int(new_brightness)))
                                sbc.set_brightness(new_brightness)
                            except Exception as e:
                                pass  # Ignore brightness control errors
                    
                    # Update previous position
                    prev_index_y = current_index_y
                else:
                    # Reset position when gesture is not active
                    prev_index_y = None
                
                # ========== VISUAL FEEDBACK ==========
                # Determine hand color based on active gesture
                if volume_gesture_active:
                    hand_color = (0, 255, 0)  # Green for volume
                    mode_text = "VOLUME"
                elif brightness_gesture_active:
                    hand_color = (255, 165, 0)  # Orange for brightness
                    mode_text = "BRIGHTNESS"
                else:
                    hand_color = (128, 128, 128)  # Gray for inactive
                    mode_text = "INACTIVE"
                
                # Draw left hand with color based on gesture state
                mp_draw.draw_landmarks(
                    frame, hand, mp_hands.HAND_CONNECTIONS,
                    mp_draw.DrawingSpec(color=hand_color, thickness=2, circle_radius=2),
                    mp_draw.DrawingSpec(color=(int(hand_color[0]*0.8), int(hand_color[1]*0.8), int(hand_color[2]*0.8)), thickness=2)
                )
                
                # Display status info
                current_vol = volume.GetMasterVolumeLevel()
                vol_percent = int((current_vol - MIN_VOL) / (MAX_VOL - MIN_VOL) * 100)
                
                try:
                    current_brightness = sbc.get_brightness()[0]
                except:
                    current_brightness = "N/A"
                
                cv2.putText(frame, f"Mode: {mode_text}", (10, 30),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, hand_color, 2)
                cv2.putText(frame, f"Volume: {vol_percent}%", (10, 60),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
                cv2.putText(frame, f"Brightness: {current_brightness}%", (10, 90),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

            # ===================== RIGHT HAND → CURSOR CONTROL (ORIGINAL LOGIC) =====================
            # ===================== RIGHT HAND → CURSOR CONTROL (MODIFIED FOR PALM CENTER) =====================
            elif hand_label == "Right":
                # Check which gesture is active FIRST
                scroll_gesture_active = check_scroll_gesture(lm)  # Index + Middle extended
                
                # ========== SCROLL CONTROL (Priority over cursor) ==========
                if scroll_gesture_active:
                    # Use the midpoint between index and middle finger for tracking
                    index_tip = lm[8]
                    middle_tip = lm[12]
                    
                    # Calculate midpoint Y position
                    current_scroll_y = (index_tip.y + middle_tip.y) / 2
                    
                    # Control scrolling based on vertical movement
                    if prev_right_index_y is not None:
                        delta_y = current_scroll_y - prev_right_index_y
                        
                        # Apply scroll if movement detected
                        if abs(delta_y) > SCROLL_DEADZONE:
                            # Calculate scroll amount
                            # Move fingers UP (decrease y) = scroll DOWN (negative)
                            # Move fingers DOWN (increase y) = scroll UP (positive)
                            scroll_amount = int(delta_y * SCROLL_SENSITIVITY)
                            
                            if scroll_amount != 0:
                                pyautogui.scroll(scroll_amount, _pause=False)
                    
                    # Update previous position
                    prev_right_index_y = current_scroll_y
                    
                    # ========== VISUAL FEEDBACK FOR SCROLL MODE ==========
                    index_x_pixel = int(index_tip.x * w)
                    index_y_pixel = int(index_tip.y * h)
                    middle_x_pixel = int(middle_tip.x * w)
                    middle_y_pixel = int(middle_tip.y * h)
                    
                    # Draw line between index and middle
                    cv2.line(frame, (index_x_pixel, index_y_pixel), 
                            (middle_x_pixel, middle_y_pixel), (0, 165, 255), 3)
                    
                    # Draw finger indicators
                    cv2.circle(frame, (index_x_pixel, index_y_pixel), 12, (0, 165, 255), -1)
                    cv2.circle(frame, (middle_x_pixel, middle_y_pixel), 12, (0, 165, 255), -1)
                    
                    # Draw hand in orange for scroll mode
                    mp_draw.draw_landmarks(
                        frame, hand, mp_hands.HAND_CONNECTIONS,
                        mp_draw.DrawingSpec(color=(0, 165, 255), thickness=2, circle_radius=2),
                        mp_draw.DrawingSpec(color=(0, 130, 200), thickness=2)
                    )
                    
                    # Display scroll mode status
                    cv2.putText(frame, "Mode: SCROLL", (10, 120),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 165, 255), 2)
                    cv2.putText(frame, "Move 2 fingers UP/DOWN", (10, 150),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
                
                # ========== CURSOR CONTROL (When NOT scrolling) ==========
                else:
                    # Reset scroll tracking when not in scroll mode
                    prev_right_index_y = None
                    
                    # Calculate PALM CENTER for cursor movement
                    wrist = lm[0]
                    middle_mcp = lm[9]  # Middle finger base (MCP joint)
                    
                    # Palm center is the midpoint between wrist and middle finger base
                    palm_x = (wrist.x + middle_mcp.x) / 2
                    palm_y = (wrist.y + middle_mcp.y) / 2
                    palm_x_pixel = int(palm_x * w)
                    palm_y_pixel = int(palm_y * h)

                    # Index finger tip (landmark 8) - for pinch detection only
                    ix, iy = int(lm[8].x * w), int(lm[8].y * h)

                    # Thumb tip (landmark 4) - for pinch detection only
                    tx, ty = int(lm[4].x * w), int(lm[4].y * h)

                    # Check if cursor should be active
                    cursor_active = check_cursor_gesture(lm)

                    # Move cursor with smoothing using PALM CENTER (only if gesture active)
                    if cursor_active:
                        raw_x, raw_y = map_to_screen(palm_x, palm_y, DEAD_ZONE_X, DEAD_ZONE_Y, SENSITIVITY_MULTIPLIER)
                        screen_x, screen_y = smooth_coordinates(raw_x, raw_y, prev_x, prev_y, smooth_factor)
                        prev_x, prev_y = screen_x, screen_y
                        
                        pyautogui.moveTo(screen_x, screen_y, _pause=False)

                    # Pinch distance (still using thumb and index)
                    distance = math.hypot(ix - tx, iy - ty)
                    
                    # Use hysteresis for more stable pinch detection
                    is_pinching = False
                    if was_pinching:
                        is_pinching = distance < RELEASE_THRESHOLD
                    else:
                        is_pinching = distance < PINCH_THRESHOLD

                    # Draw pinch visualization
                    color = (0, 255, 0) if is_pinching else (255, 0, 0)
                    cv2.line(frame, (ix, iy), (tx, ty), color, 2)
                    cv2.circle(frame, (ix, iy), 8, (255, 0, 255), -1)
                    cv2.circle(frame, (tx, ty), 8, (255, 255, 0), -1)
                    
                    # Draw PALM CENTER indicator
                    cv2.circle(frame, (palm_x_pixel, palm_y_pixel), 15, (0, 255, 255), 3)
                    cv2.circle(frame, (palm_x_pixel, palm_y_pixel), 5, (0, 255, 255), -1)
                    cv2.putText(frame, "PALM", (palm_x_pixel + 20, palm_y_pixel), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 2)

                    # Click cooldown management
                    if click_cooldown > 0:
                        click_cooldown = max(0, click_cooldown - (1/fps if fps > 0 else 0.03))

                    # Reset click count if too much time has passed
                    current_time = time.time()
                    if current_time - last_click_completed_time > CLICK_RESET_TIME:
                        click_count = 0

                    if is_pinching:
                        if pinch_start_time is None:
                            pinch_start_time = time.time()

                        elif time.time() - pinch_start_time >= HOLD_TIME:
                            if not mouse_down:
                                pyautogui.mouseDown(_pause=False)
                                mouse_down = True
                                click_count = 0
                                print("Drag started")

                    else:  # Not pinching
                        if pinch_start_time is not None:
                            pinch_duration = time.time() - pinch_start_time
                            
                            # Handle drag release
                            if mouse_down:
                                pyautogui.mouseUp(_pause=False)
                                mouse_down = False
                                click_count = 0
                                print("Drag ended")
                            
                            # Handle clicks (quick pinches only)
                            elif pinch_duration < HOLD_TIME and click_cooldown == 0:
                                click_count += 1
                                last_click_completed_time = current_time
                                
                                if click_count == 1:
                                    last_click_time = current_time
                                    print("Click 1 detected, waiting for second click...")
                                    
                                elif click_count == 2:
                                    time_since_first = current_time - last_click_time
                                    
                                    if time_since_first < DOUBLE_CLICK_TIME:
                                        pyautogui.doubleClick(_pause=False)
                                        print("✓ DOUBLE CLICK!")
                                        click_cooldown = COOLDOWN_TIME
                                        click_count = 0
                                    else:
                                        pyautogui.click(_pause=False)
                                        print("Single Click (too slow for double)")
                                        click_count = 1
                                        last_click_time = current_time
                                        click_cooldown = COOLDOWN_TIME
                                
                                else:
                                    pyautogui.click(_pause=False)
                                    print("Single Click")
                                    click_count = 0
                                    click_cooldown = COOLDOWN_TIME

                        pinch_start_time = None
                    
                    # Execute pending single click after timeout
                    if click_count == 1 and (current_time - last_click_time) > DOUBLE_CLICK_TIME:
                        pyautogui.click(_pause=False)
                        print("Single Click (timeout)")
                        click_count = 0
                        click_cooldown = COOLDOWN_TIME
                    
                    was_pinching = is_pinching

                    # Draw hand landmarks (right hand in magenta)
                    mp_draw.draw_landmarks(
                        frame, hand, mp_hands.HAND_CONNECTIONS,
                        mp_draw.DrawingSpec(color=(255, 0, 255), thickness=2, circle_radius=2),
                        mp_draw.DrawingSpec(color=(200, 0, 200), thickness=2)
                    )

                    # Display cursor status with click counter
                    cursor_status = "ACTIVE" if cursor_active else "STOPPED"
                    
                    if mouse_down:
                        status = "DRAGGING"
                    elif is_pinching:
                        status = f"PINCHING"
                    elif click_count > 0:
                        status = f"CLICK {click_count}/2"
                    else:
                        status = "READY"
                    
                    cv2.putText(frame, f"Cursor: {cursor_status}", (10, 120),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0) if cursor_active else (0, 165, 255), 2)
                    cv2.putText(frame, f"Action: {status}", (10, 150),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
                    cv2.putText(frame, f"Distance: {int(distance)}", (10, 180),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
    else:
        cv2.putText(frame, "No hand detected", (10, 30),
                   cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)

    # Reset left hand angle if left hand is not detected
    if not left_hand_detected:
        prev_left_angle = None

    # Display FPS
    cv2.putText(frame, f"FPS: {int(fps)}", (10, h - 10),
               cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2)

    cv2.imshow("Hand Mouse + Volume Control", frame)
    if cv2.waitKey(1) & 0xFF == 27:
        running = False
        break

cap.release()
cv2.destroyAllWindows()
print("\nHand Control Stopped")
