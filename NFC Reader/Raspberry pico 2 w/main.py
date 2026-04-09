"""
WPI405 (MFRC522) NFC Reader/Writer for Raspberry Pi Pico 2W
Pinout Reference guide
  SCK  -> GP2
  MOSI -> GP3
  MISO -> GP4
  RST  -> GP0
  CS   -> GP5
"""

from mfrc522 import MFRC522
from machine import Pin
import network
import urequests
import time

reader = MFRC522(sck=2, mosi=3, miso=4, rst=0, cs=5)
led = Pin(15, Pin.OUT)

# ------------------------------
# WIFI
# ------------------------------
WIFI_SSID = "JOUW_WIFI_NAAM"
WIFI_PASSWORD = "JOUW_WIFI_WACHTWOORD"

# Gebruik het lokale IP-adres van je laptop
SERVER_URL = "http://192.168.1.100:5000/scan_nfc"

# Toegestane UID's
ALLOWED_UIDS = [
    "65:BD:66:75:CB",
]

# Kleine cooldown tegen dubbel scannen
SCAN_COOLDOWN = 3
last_scan_uid = None
last_scan_time = 0


def uid_to_str(uid):
    return ":".join(f"{b:02X}" for b in uid)


def connect_wifi():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)

    if not wlan.isconnected():
        print("Connecting to WiFi...")
        wlan.connect(WIFI_SSID, WIFI_PASSWORD)

        timeout = 15
        while timeout > 0 and not wlan.isconnected():
            time.sleep(1)
            timeout -= 1

    if wlan.isconnected():
        print("WiFi connected")
        print("Pico IP:", wlan.ifconfig()[0])
        return True

    print("WiFi connection failed")
    return False


def send_uid_to_server(uid_str):
    try:
        payload = {"uid": uid_str}
        response = urequests.post(SERVER_URL, json=payload)

        status_code = response.status_code
        response_text = response.text
        print("Server response:", response_text)

        response.close()

        if status_code == 200:
            return True
        else:
            print("Server rejected scan")
            return False

    except Exception as e:
        print("Error sending to server:", e)
        return False


def scan_allowed(uid_str):
    global last_scan_uid, last_scan_time

    now = time.time()

    if uid_str == last_scan_uid and (now - last_scan_time) < SCAN_COOLDOWN:
        print("Same tag scanned too quickly, ignoring...")
        return False

    last_scan_uid = uid_str
    last_scan_time = now
    return True


def read_uid():
    """Read UID only — scans once then returns to menu."""
    print("Waiting for card (UID only)...")

    while True:
        reader.init()
        status, _ = reader.request(reader.REQIDL)

        if status == reader.OK:
            status, uid = reader.anticoll()

            if status == reader.OK:
                uid_str = uid_to_str(uid)
                print("UID:", uid_str)

                if uid_str not in ALLOWED_UIDS:
                    print("UID not in allowed list")
                    return

                if not scan_allowed(uid_str):
                    return

                print("Access granted!")
                success = send_uid_to_server(uid_str)

                if success:
                    print("Return processed successfully")
                    led.on()
                    time.sleep(2)
                    led.off()
                else:
                    print("Could not update Flask server or item was not on loan")

                return


def read_card(key=None):
    """Read UID + data block 8 — scans once then returns to menu."""
    if key is None:
        key = [0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF]

    print("Waiting for card...")

    while True:
        reader.init()
        status, _ = reader.request(reader.REQIDL)

        if status == reader.OK:
            status, uid = reader.anticoll()

            if status == reader.OK:
                uid_str = uid_to_str(uid)
                print("\nCard UID:", uid_str)

                if uid_str not in ALLOWED_UIDS:
                    print("UID not in allowed list")
                    led.off()
                    return

                if not scan_allowed(uid_str):
                    return

                print("Access granted!")
                success = send_uid_to_server(uid_str)

                if success:
                    led.on()
                else:
                    print("Could not update Flask server or item was not on loan")
                    led.off()

                reader.select_tag(uid)

                if reader.auth(reader.AUTHENT1A, 8, key, uid) == reader.OK:
                    data = reader.read(8)
                    if data:
                        text = bytes(data).decode("utf-8").rstrip("\x00")
                        print("Data:", text)
                    else:
                        print("Could not read block 8")
                else:
                    print("Auth failed — wrong key?")

                reader.stop_crypto1()
                time.sleep(1)
                led.off()
                return


def write_card(text, key=None):
    """Write text to block 8 (max 16 chars)."""
    if key is None:
        key = [0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF]

    raw = text.encode("utf-8")[:16]
    data = list(raw) + [0x00] * (16 - len(raw))

    print("Hold card to write '{}'... press Ctrl+C to cancel".format(text))

    while True:
        reader.init()
        status, _ = reader.request(reader.REQIDL)

        if status == reader.OK:
            status, uid = reader.anticoll()

            if status == reader.OK:
                print("Card UID:", uid_to_str(uid))
                reader.select_tag(uid)

                if reader.auth(reader.AUTHENT1A, 8, key, uid) == reader.OK:
                    result = reader.write(8, data)
                    if result == reader.OK:
                        print("Written:", text)
                    else:
                        print("Write failed")
                else:
                    print("Auth failed — wrong key?")

                reader.stop_crypto1()
                return


def menu():
    print("\n=== WPI405 NFC - Pico 2W ===")
    print("1. Read UID only")
    print("2. Read UID + data")
    print("3. Write text to card")
    print("0. Quit")
    choice = input("Choose: ").strip()

    if choice == "1":
        read_uid()
    elif choice == "2":
        read_card()
    elif choice == "3":
        text = input("Text to write (max 16 chars): ").strip()
        if text:
            write_card(text)
    elif choice == "0":
        print("Goodbye!")
        led.off()
        raise SystemExit
    else:
        print("Invalid choice")


if connect_wifi():
    while True:
        menu()
else:
    print("No WiFi connection. Flask update will not work.")