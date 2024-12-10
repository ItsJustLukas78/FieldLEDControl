import cv2
import pytesseract
import time
import threading
import requests
import re

# Configure Tesseract
pytesseract.pytesseract.tesseract_cmd = r'/opt/homebrew/bin/tesseract'

FLASK_SERVER_URL = "http://192.168.2.2:5000/state/"

# Define Match States
class MatchState:
    SCHEDULED_START = "SCHEDULED_START"
    MATCH_STARTING = "MATCH_STARTING"
    AUTONOMOUS = "AUTONOMOUS"
    DRIVER_CONTROL = "DRIVER_CONTROL"
    AUTO_END = "AUTO_END"
    DRIVER_END = "DRIVER_END"
    IDLE = "IDLE"

# Initialize Current State
current_state = MatchState.IDLE

# Initialize LED Controller (Replace with actual implementation)
class LEDController:
    def set_pattern(self, pattern_name):
        print(f"Setting LED pattern: {pattern_name}")

led_controller = LEDController()

def send_state_to_server(state, timer_value=None):
    print(f"Sending state to server: {state}, timer_value: {timer_value}")
    """Send the current match state to the Flask server to trigger the LED effect."""
    state_url = FLASK_SERVER_URL + state + f"/{timer_value}"
    try:
        response = requests.get(state_url)
        if response.status_code == 200:
            print(f"State {state} executed successfully!")
        else:
            print(f"Failed to trigger state {state}. Status code: {response.status_code}")
    except requests.exceptions.RequestException as e:
        print(f"Error sending state to server: {e}")

# Example: Send different states to the server based on match progress
def handle_match_state(state, timer_value=None):
    if state == MatchState.SCHEDULED_START:
        send_state_to_server(MatchState.SCHEDULED_START)
    elif state == MatchState.MATCH_STARTING:
        send_state_to_server(MatchState.MATCH_STARTING)
    elif state == MatchState.AUTONOMOUS:
        send_state_to_server(MatchState.AUTONOMOUS, timer_value)
    elif state == MatchState.DRIVER_CONTROL:
        send_state_to_server(MatchState.DRIVER_CONTROL, timer_value)
    elif state == MatchState.AUTO_END:
        send_state_to_server(MatchState.AUTO_END)
    elif state == MatchState.DRIVER_END:
        send_state_to_server(MatchState.DRIVER_END)
    else:
        send_state_to_server(MatchState.IDLE)

# # Function to Update State After Timer Reaches 0
# def update_state_on_timer_end():
#     global current_state
#     if current_state == MatchState.AUTONOMOUS:
#         current_state = MatchState.AUTO_END
#         handle_match_state(current_state)
#         time.sleep(5)  # Flash lights for 5 seconds
#         current_state = MatchState.IDLE
#         handle_match_state(current_state)
#     elif current_state == MatchState.DRIVER_CONTROL:
#         current_state = MatchState.DRIVER_END
#         handle_match_state(current_state)
#         time.sleep(5)  # Flash lights for 5 seconds
#         current_state = MatchState.IDLE
#         handle_match_state(current_state)

def extract_timer(timer_text):
    timer_match = re.match(r'(\d+):(\d+)', timer_text)
    if timer_match:
        minutes = int(timer_match.group(1))
        seconds = int(timer_match.group(2))
        total_seconds = minutes * 60 + seconds

        print(f"Timer: {total_seconds} seconds")

        return total_seconds

# Function to Detect Match State and Timer
def detect_match_state(frame, previous_timer_value):
    global current_state
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    detected_state = MatchState.IDLE

    height, width = frame.shape[:2]
    ROIs = {
        "bottom_text": (int(width * 0), int(height * 0.92), int(width * 1), int(height * 1)),
        "timer": (int(width * 0.2), int(height * 0.3), int(width * 0.8), int(height * 0.75)),
    }

    # Extract and Process Bottom Text
    x1, y1, x2, y2 = ROIs["bottom_text"]
    bottom_text_img = gray[y1:y2, x1:x2]
    bottom_text = pytesseract.image_to_string(bottom_text_img, config='--psm 7').strip().lower()

    # Extract and Process Timer
    x1, y1, x2, y2 = ROIs["timer"]
    timer_img = gray[y1:y2, x1:x2]
    timer_text = pytesseract.image_to_string(timer_img, config='--psm 7').strip()

    timer_value = None

    try:
        # Attempt to parse the timer value
        timer_value = extract_timer(timer_text)
    except Exception as e:
        print(f"Error extracting timer: {e}")
        timer_value = None

    # # Draw Debugging Bounding Boxes
    # for roi_name, (x1, y1, x2, y2) in ROIs.items():
    #     cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
    #     cv2.putText(frame, roi_name, (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)

    # Determine State Based on Bottom Text
    if "scheduled start" in bottom_text:
        detected_state = MatchState.SCHEDULED_START
    elif "match starting" in bottom_text:
        detected_state = MatchState.MATCH_STARTING
    elif "autonomous" in bottom_text:
        detected_state = MatchState.AUTONOMOUS
    elif "driver control" in bottom_text:
        detected_state = MatchState.DRIVER_CONTROL
    else:
        detected_state = MatchState.IDLE

    # Update State and LED Pattern
    if detected_state != current_state:
        current_state = detected_state
        handle_match_state(current_state, timer_value)

    # # Only update state when timer transitions from 1 to 0
    # if timer_value is not None and previous_timer_value == 1 and timer_value == 0:
    #     update_state_on_timer_end()

    return timer_value

# Main Program
def main():
    previous_timer_value = None

    # Capture Video from Virtual Webcam
    cap = cv2.VideoCapture(2)  # Replace '0' with OBS virtual webcam index if needed

    if not cap.isOpened():
        print("Error: Unable to access webcam.")
        return

    print("Starting Match State Detection...")
    try:
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break

            # Detect Match State and Timer
            previous_timer_value = detect_match_state(frame, previous_timer_value)

            # # Display Frame for Debugging (Optional)
            # cv2.imshow("Match State Detection", frame)

            # Exit on 'q' Key
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
    finally:
        cap.release()
        cv2.destroyAllWindows()

# Run the Program
if __name__ == "__main__":
    main()
