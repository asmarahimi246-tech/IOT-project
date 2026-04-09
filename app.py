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
import time

reader = MFRC522(sck=2, mosi=3, miso=4, rst=0, cs=5)

led = Pin(15, Pin.OUT)

# add uid here replace with database later #
ALLOWED_UIDS = [
    "65:BD:66:75:CB",  # replace or add more UIDs as needed
]


def uid_to_str(uid):
    return ":".join(f"{b:02X}" for b in uid)


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
                print(f"  UID: {uid_str}")
                if uid_str in ALLOWED_UIDS:
                    print("  Access granted!")
                    led.on()
                    time.sleep(3)
                    led.off()
                else:
                    print("  UID not in allowed list")
                return  # back to menu


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
                print(f"\n  Card UID: {uid_to_str(uid)}")
                if uid_to_str(uid) in ALLOWED_UIDS:
                    print("  Access granted!")
                    led.on()
                else:
                    print("  UID not in allowed list")
                    led.off()
                reader.select_tag(uid)

                if reader.auth(reader.AUTHENT1A, 8, key, uid) == reader.OK:
                    data = reader.read(8)
                    if data:
                        text = bytes(data).decode("utf-8").rstrip("\x00")
                        print(f"  Data: {text}")
                    else:
                        print("  Could not read block 8")
                else:
                    print("  Auth failed — wrong key?")

                reader.stop_crypto1()
                time.sleep(1)
                led.off()
                return  # back to menu


def write_card(text, key=None):
    """Write text to block 8 (max 16 chars)."""
    if key is None:
        key = [0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF]

    raw = text.encode("utf-8")[:16]
    data = list(raw) + [0x00] * (16 - len(raw))

    print(f"Hold card to write '{text}'... press Ctrl+C to cancel")
    while True:
        reader.init()
        status, _ = reader.request(reader.REQIDL)
        if status == reader.OK:
            status, uid = reader.anticoll()
            if status == reader.OK:
                print(f"  Card UID: {uid_to_str(uid)}")
                reader.select_tag(uid)

                if reader.auth(reader.AUTHENT1A, 8, key, uid) == reader.OK:
                    result = reader.write(8, data)
                    if result == reader.OK:
                        print(f"  Written: {text}")
                    else:
                        print("  Write failed")
                else:
                    print("  Auth failed — wrong key?")

                reader.stop_crypto1()
                return  # write once then exit


# Tracks active rentals: { uid_str: item_name }
# In production this would sync with the database/API
active_rentals = {}


def checkout_item(uid_str, item_name):
    """Register a rental as active (call this after a successful reservation)."""
    active_rentals[uid_str] = item_name
    print(f"  Checked out '{item_name}' to card {uid_str}")


def return_item(key=None):
    """Scan a card to return a rented item."""
    if key is None:
        key = [0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF]

    print("Scan card to return item... press Ctrl+C to cancel")
    while True:
        reader.init()
        status, _ = reader.request(reader.REQIDL)
        if status == reader.OK:
            status, uid = reader.anticoll()
            if status == reader.OK:
                uid_str = uid_to_str(uid)
                print(f"\n  Card UID: {uid_str}")

                if uid_str not in active_rentals:
                    print("  No active rental found for this card.")
                    led.off()
                    return

                # Optionally read block 8 to confirm item name written on card
                item_name = active_rentals[uid_str]
                reader.select_tag(uid)
                if reader.auth(reader.AUTHENT1A, 8, key, uid) == reader.OK:
                    data = reader.read(8)
                    if data:
                        written_name = bytes(data).decode("utf-8").rstrip("\x00")
                        print(f"  Card data: {written_name}")
                    reader.stop_crypto1()

                # Mark as returned
                del active_rentals[uid_str]
                print(f"  Item '{item_name}' successfully returned!")
                led.on()
                time.sleep(2)
                led.off()
                return


def menu():
    print("\n=== WPI405 NFC - Pico 2W ===")
    print("1. Read UID only")
    print("2. Read UID + data")
    print("3. Write text to card")
    print("4. Return item")
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
    elif choice == "4":
        return_item()
    elif choice == "0":
        print("Goodbye!")
        led.off()
        raise SystemExit
    else:
        print("Invalid choice")


while True:
    menu()