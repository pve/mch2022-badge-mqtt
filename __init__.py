"""
mqtt_display.py — MCH2022 Badge MQTT Subscriber
Connects to WiFi, subscribes to an MQTT topic, and displays
incoming messages on the badge screen.

Configuration: edit the constants below before uploading.
"""

import display
import wifi
import utime
import buttons
import mch22

from umqtt.simple import MQTTClient

# ── Configuration ─────────────────────────────────────────────────────────────
MQTT_BROKER   = "dockerpi.griddlejuiz.com"   # Hostname or IP of your MQTT broker
MQTT_PORT     = 1883                   # 1883 = plain, 8883 = TLS
MQTT_TOPIC    = b"mch2022/badge/test" # Topic to subscribe to (bytes)
MQTT_CLIENT_ID = b"mch2022_badge"     # Must be unique per broker session
MQTT_USER     = None                   # Set to b"user" if broker needs auth
MQTT_PASSWORD = None                   # Set to b"pass" if broker needs auth

RECONNECT_DELAY_S = 5                  # Seconds to wait before reconnecting
# ──────────────────────────────────────────────────────────────────────────────

# Display dimensions (MCH2022 LCD is 320×240)
W = display.width()
H = display.height()

# Colour palette
COL_BG      = 0x1a1a2e   # Dark blue background
COL_HEADER  = 0x16213e   # Slightly lighter header bar
COL_ACCENT  = 0x0f3460   # Accent border
COL_TOPIC   = 0x53d8fb   # Cyan — topic label
COL_MSG     = 0xffffff   # White — message body
COL_STATUS  = 0x888888   # Grey — status line
COL_OK      = 0x44cc66   # Green — connected indicator
COL_ERR     = 0xff4444   # Red — error indicator

FONT_BIG    = "permanentmarker22"
FONT_MED    = "roboto_regular18"
FONT_SMALL  = "7x5"

def on_home(pressed):
    if pressed:
        mch22.exit_python()

buttons.attach(buttons.BTN_HOME, on_home)

MAX_HISTORY = 6           # Lines of message history to keep
message_history = []      # list of (topic_str, payload_str)
status_text     = "Starting..."
status_ok       = False


def draw_screen():
    """Render the full badge display."""
    display.drawFill(COL_BG)

    # Header bar
    display.drawRect(0, 0, W, 28, True, COL_HEADER)
    display.drawText(6, 4, "MQTT Monitor", COL_TOPIC, FONT_MED)

    # Topic label
    topic_str = MQTT_TOPIC.decode()
    display.drawText(6, 34, "Topic: " + topic_str, COL_TOPIC, FONT_SMALL)

    # Status / connection indicator
    indicator = COL_OK if status_ok else COL_ERR
    display.drawRect(W - 14, 6, 10, 10, True, indicator)
    display.drawText(6, H - 16, status_text, COL_STATUS, FONT_SMALL)

    # Message history — newest at the top
    y = 52
    line_h = 28
    for topic, msg in reversed(message_history):
        if y + line_h > H - 20:
            break
        # Dim separator line
        display.drawLine(6, y - 3, W - 6, y - 3, COL_ACCENT)
        colour = COL_ERR if topic == "ERR" else COL_MSG
        prefix = "ERR: " if topic == "ERR" else ""
        display.drawText(6, y, prefix + msg, colour, FONT_SMALL)
        y += line_h

    display.flush()


def set_status(text, ok=True):
    global status_text, status_ok
    status_text = text
    status_ok   = ok
    draw_screen()


def on_message(topic, msg):
    """Callback fired by umqtt when a message arrives."""
    t = topic.decode("utf-8", "replace")
    m = msg.decode("utf-8", "replace")

    # Keep history bounded
    message_history.append((t, m))
    if len(message_history) > MAX_HISTORY:
        message_history.pop(0)

    draw_screen()


def connect_wifi():
    set_status("Connecting WiFi…", ok=False)
    wifi.connect()
    # wifi.connect() blocks until connected or raises
    set_status("WiFi OK", ok=True)
    utime.sleep_ms(500)


def connect_mqtt():
    set_status("Connecting MQTT…", ok=False)
    client = MQTTClient(
        client_id=MQTT_CLIENT_ID,
        server=MQTT_BROKER,
        port=MQTT_PORT,
        user=MQTT_USER,
        password=MQTT_PASSWORD,
        keepalive=30,
    )
    client.set_callback(on_message)
    client.connect()
    client.subscribe(MQTT_TOPIC)
    set_status("Listening: " + MQTT_TOPIC.decode(), ok=True)
    return client


def main():
    connect_wifi()

    client = None
    while True:
        try:
            if client is None:
                client = connect_mqtt()

            # check_msg() is non-blocking; returns immediately if no message
            client.check_msg()
            utime.sleep_ms(100)

        except OSError as e:
            err = str(e)
            message_history.append(("ERR", err))
            if len(message_history) > MAX_HISTORY:
                message_history.pop(0)
            set_status("Reconnecting…", ok=False)
            try:
                client.disconnect()
            except Exception:
                pass
            client = None
            utime.sleep(RECONNECT_DELAY_S)

        except KeyboardInterrupt:
            set_status("Stopped", ok=False)
            if client:
                client.disconnect()
            break


main()