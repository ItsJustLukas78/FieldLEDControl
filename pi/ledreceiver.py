import time
import flask
from rpi_ws281x import PixelStrip, Color
import threading

# LED strip configuration:
LED_COUNT = 1200        # Number of LED pixels.
LED_PIN = 18          # GPIO pin connected to the pixels (18 uses PWM!).
LED_FREQ_HZ = 800000   # LED signal frequency in hertz (usually 800khz)
LED_DMA = 10           # DMA channel to use for generating signal (try 10)
LED_BRIGHTNESS = 50    # Set to 0 for darkest and 255 for brightest
LED_INVERT = False     # True to invert the signal (when using NPN transistor level shift)
LED_CHANNEL = 0        # set to '1' for GPIOs 13, 19, 41, 45 or 53

app = flask.Flask(__name__)
strip = PixelStrip(LED_COUNT, LED_PIN, LED_FREQ_HZ, LED_DMA, LED_INVERT, LED_BRIGHTNESS, LED_CHANNEL)

# Event to manage ongoing effect cancellation
effect_event = threading.Event()
effect_thread = None

# LED effects
def neutralEffect(strip):
    """Neutral effect - all LEDs off but still lit with a faint color."""
    for i in range(strip.numPixels()):
        strip.setPixelColor(i, Color(150, 150, 150))
    strip.show()

#function that smoothly transitions to one color to another in 1 second, with the start color being whatever the current color is
def transitionToColor(strip, start_color, end_color):
    i = 0
    while i < 256:
        r = int((i / 255) * (end_color >> 16) + (1 - (i / 255)) * (start_color >> 16))
        g = int((i / 255) * ((end_color >> 8) & 255) + (1 - (i / 255)) * ((start_color >> 8) & 255))
        b = int((i / 255) * (end_color & 255) + (1 - (i / 255)) * (start_color & 255))
        for j in range(strip.numPixels()):
            strip.setPixelColor(j, Color(r, g, b))
        strip.show()
        time.sleep(0.004)
        i += 4
    return "good"

def countdown(duration_s=10, blue_color=Color(0, 0, 255), red_color=Color(255, 0, 0), flash=True, delay=0.50):
    global strip

    # Calculate the size of each equal section
    section_size = 50
    num_sections = strip.numPixels() // section_size

    # # Set the color of the entire strip to  blue
    # for i in range(strip.numPixels()):
    #     strip.setPixelColor(i, blue_color)
    #
    # if effect_event.is_set(): return  # Stop the effect if a new one is triggered
    # strip.show()

    # each section to be completely blue at the start, and as time progresses, the MIDDLE OF EACH SECTION turns red and grows outward towards the edge of its own section

    # Array indicating the color of each led, 1 for blue, 0 for red
    led_colors = [1] * strip.numPixels()

    # set each middle pixel to red
    for section in range(num_sections):
        if effect_event.is_set(): return  # Stop the effect if a new one is triggered
        center_pixel = section * section_size + section_size // 2
        led_colors[center_pixel] = 0

    # Change the color of the sections to red from the middle outward each second
    for i in range(1, duration_s + 1):
        if effect_event.is_set(): return  # Stop the effect if a new one is triggered

        # if duration isnt 15 and the current i is 15, make a more dramatic change at 15 seconds, then continue doing the normal change. Flash dark yellow to off 4 times in 1 second
        if duration_s != 15 and i == duration_s - 15:
            for j in range(4):
                wait_time = (1/2) * ((1/3) * (1 - (delay / duration_s)))
                if effect_event.is_set(): return
                for led in range(strip.numPixels()):
                    strip.setPixelColor(led, Color(255, 255, 0))
                strip.show()
                time.sleep(wait_time)
                if effect_event.is_set(): return
                neutralEffect(strip)
                time.sleep(wait_time)
                if effect_event.is_set(): return


            continue

        # generate new led_colors
        for section in range(num_sections):
            center_pixel = section * section_size + section_size // 2
            # calculate the number of pixels to turn red in the current iteration, which has to be proportional to the distance from the center pixel and the time elapsed
            pixels_to_infect = (i / duration_s) * (section_size // 2)

            pixels_to_infect = int(pixels_to_infect)

            # change # pixels to left and right of center pixel to red according to pixels_to_infect
            for offset in range(1, pixels_to_infect + 1):
                left_pixel = center_pixel - offset
                right_pixel = center_pixel + offset

                try:
                    led_colors[left_pixel] = 0
                except:
                    pass

                try:
                    led_colors[right_pixel] = 0
                except:
                    pass

        for led in range(strip.numPixels()):
            if effect_event.is_set(): return  # Stop the effect if a new one is triggered
            if led_colors[led] == 0:
                strip.setPixelColor(led, red_color)
            else:
                strip.setPixelColor(led, blue_color)

        if i == duration_s:
            # flash the lights red on and off
            for led in range(strip.numPixels()):
                strip.setPixelColor(led, red_color)
            strip.show()

            if flash:
                for j in range(4):
                    if effect_event.is_set(): return  # Stop the effect if a new one is triggered
                    time.sleep(0.2)
                    if effect_event.is_set(): return
                    neutralEffect(strip)
                    time.sleep(0.2)
                    if effect_event.is_set(): return
                    for led in range(strip.numPixels()):
                        strip.setPixelColor(led, red_color)
                    strip.show()
        else:
            strip.show()
            time.sleep(1 - (delay / duration_s))
    return "good"

# Function to trigger effect in a background thread
def trigger_effect_in_background(state, time_left):
    """Trigger the appropriate effect based on the state"""

    if state == "SCHEDULED_START":
        neutralEffect(strip)
    elif state == "MATCH_STARTING":
        countdown(3, Color(50, 50, 50), Color(255, 255, 0), False)
    elif state == "AUTONOMOUS":
        transitionToColor(strip, Color(255, 255, 0), Color(0, 255, 0))
        countdown(int(time_left) if time_left else 15, Color(0, 255, 0), Color(255, 0, 0))
    elif state == "DRIVER_CONTROL":
        transitionToColor(strip, Color(255, 255, 0), Color(0, 0, 255))
        countdown(int(time_left) if time_left else 105)
    elif state == "AUTO_END":
        pass
    elif state == "DRIVER_END":
        pass
    else:
        neutralEffect(strip)

@app.route('/state/<state>/<time_left>', methods=['GET'])
def handle_state_change(state, time_left=None):
    """Handle the state change and trigger the corresponding LED effect."""
    # Run the LED effect in a background thread and interrupt the previous effect immediately
    if state == "IDLE":
        time.sleep(1.6)

    global effect_thread
    global effect_event

    if effect_event:
        effect_event.set()

    if effect_thread:
        effect_thread.join()

    effect_event.clear()  # Reset the event, allowing the effect to run

    effect_thread = threading.Thread(target=trigger_effect_in_background, args=(state,time_left,))
    effect_thread.start()

    # Return a 200 OK response immediately
    return f"Effect for state {state} executed!", 200

@app.route('/brightness/<int:brightness>', methods=['GET'])
def setBrightness(brightness=50):
    """Adjust brightness of LEDs."""
    if brightness < 0 or brightness > 255:
        return "bad"
    strip.setBrightness(brightness)
    strip.show()
    return "good"

@app.route('/color/<color>', methods=['GET'])
def setColor(color=0):
    """Set the color of the LEDs."""
    if color == "red":
        color = Color(255, 0, 0)
    elif color == "green":
        color = Color(0, 255, 0)
    elif color == "blue":
        color = Color(0, 0, 255)
    elif color == "white":
        color = Color(255, 255, 255)

    transitionToColor(strip, Color(50, 50, 50), color)
    return "good"


# Main program logic follows:
if __name__ == '__main__':
    # Initialize the library
    strip.begin()

    # Start with a neutral effect
    neutralEffect(strip)

    # Run the Flask app
    app.run(host='0.0.0.0', port=5000, debug=True)
