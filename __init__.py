"""
MCH2022 Badge — Power Monitor
Displays PV output, grid flow, and home consumption from MQTT JSON.
Payload format: {"pv": W, "cons": W, "prod": W}
"""

import display
import wifi
import utime
import buttons
import mch22
import ujson

from umqtt.simple import MQTTClient

# ── Configuration ─────────────────────────────────────────────────────────────
MQTT_BROKER    = "dockerpi.griddlejuiz.com"
MQTT_PORT      = 1883
MQTT_TOPIC     = b"mch2022/badge/test"
MQTT_CLIENT_ID = b"mch2022_badge"
MQTT_USER      = None
MQTT_PASSWORD  = None
RECONNECT_DELAY_S = 5
# ──────────────────────────────────────────────────────────────────────────────

W = display.width()
H = display.height()

COL_BG      = 0x331a38
COL_HEADER  = 0x491d88
COL_ACCENT  = 0x491d88
COL_TRACE   = 0x4a2070
COL_LABEL   = 0xfa448c
COL_WHITE   = 0xfec859
COL_STATUS  = 0x43b5a0
COL_OK      = 0x43b5a0
COL_ERR     = 0xfa448c
COL_GREEN   = 0x43b5a0
COL_RED     = 0xfa448c

FONT_BIG    = "exo2_bold22"
FONT_MED    = "roboto_regular12"
FONT_SMALL  = "7x5"

def on_home(pressed):
    if pressed:
        mch22.exit_python()

buttons.attach(buttons.BTN_HOME, on_home)

pv_w       = None
cons_w     = None
prod_w     = None
status_text = "Starting..."
status_ok   = False
last_topic  = MQTT_TOPIC.decode()


def draw_bg():
    display.drawFill(COL_BG)
    spacing = 24
    for x in range(-H, W, spacing):
        display.drawLine(x, 0, x + H, H, COL_TRACE)
    for x in range(0, W + H, spacing):
        display.drawLine(x, 0, x - H, H, COL_TRACE)


def draw_screen():
    draw_bg()

    # Header
    display.drawRect(0, 0, W, 26, True, COL_HEADER)
    display.drawText(6, 4, "Power Monitor", COL_LABEL, FONT_MED)
    dot = COL_OK if status_ok else COL_ERR
    display.drawRect(W - 14, 7, 10, 10, True, dot)

    if pv_w is None:
        display.drawText(6, 60, "Waiting for data...", COL_STATUS, FONT_MED)
        display.drawText(6, H - 14, status_text, COL_STATUS, FONT_SMALL)
        display.flush()
        return

    # ── PV row ────────────────────────────────────────────────────────────────
    display.drawText(6, 30, "Solar PV", COL_LABEL, FONT_MED)
    display.drawText(6, 44, str(pv_w) + " W", COL_WHITE, FONT_BIG)

    # ── Grid row ──────────────────────────────────────────────────────────────
    grid_x = W // 2 + 4
    display.drawText(grid_x, 30, "Grid", COL_LABEL, FONT_MED)

    if prod_w and prod_w > 0:
        grid_val = prod_w
        grid_col = COL_GREEN
        grid_dir = "^ "
    elif cons_w and cons_w > 0:
        grid_val = cons_w
        grid_col = COL_RED
        grid_dir = "v "
    else:
        grid_val = 0
        grid_col = COL_WHITE
        grid_dir = "  "

    display.drawText(grid_x, 44, grid_dir + str(grid_val) + " W", grid_col, FONT_BIG)

    # Divider
    display.drawLine(6, 92, W - 6, 92, COL_ACCENT)

    # ── Home use row ──────────────────────────────────────────────────────────
    home_w = (pv_w or 0) + (cons_w or 0) - (prod_w or 0)
    display.drawText(6, 96, "Home use", COL_LABEL, FONT_MED)
    display.drawText(6, 110, str(home_w) + " W", COL_WHITE, FONT_BIG)

    # ── Diagnostics ───────────────────────────────────────────────────────────
    display.drawLine(6, H - 22, W - 6, H - 22, COL_ACCENT)
    display.drawText(6, H - 16, status_text + "  " + last_topic, COL_STATUS, FONT_SMALL)

    display.flush()


def set_status(text, ok=True):
    global status_text, status_ok
    status_text = text
    status_ok   = ok
    draw_screen()


def on_message(topic, msg):
    global pv_w, cons_w, prod_w, last_topic
    last_topic = topic.decode("utf-8", "replace")
    try:
        data  = ujson.loads(msg)
        pv_w   = int(data.get("pv",   0))
        cons_w = int(data.get("cons", 0))
        prod_w = int(data.get("prod", 0))
    except Exception:
        pass
    draw_screen()


def connect_wifi():
    set_status("Connecting WiFi...", ok=False)
    wifi.connect()
    set_status("WiFi OK", ok=True)
    utime.sleep_ms(500)


def connect_mqtt():
    set_status("Connecting MQTT...", ok=False)
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
    set_status("OK", ok=True)
    return client


def main():
    connect_wifi()
    client = None
    while True:
        try:
            if client is None:
                client = connect_mqtt()
            client.check_msg()
            utime.sleep_ms(100)
        except OSError:
            set_status("Reconnecting...", ok=False)
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
