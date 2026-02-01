import random
import time

import uiautomator2 as u2


TIKTOK_PACKAGE = "com.zhiliaoapp.musically"


def log(msg: str):
    ts = time.strftime("%H:%M:%S")
    print(f"[{ts}] {msg}")


def auto_detect_device_serial() -> str:
    import subprocess
    try:
        result = subprocess.run(
            ["adb", "devices"],
            capture_output=True,
            text=True,
            check=False
        )
    except Exception:
        return ""
    lines = result.stdout.splitlines()
    devices = []
    for line in lines[1:]:
        line = line.strip()
        if not line:
            continue
        if "\tdevice" in line:
            devices.append(line.split("\t")[0].strip())
    if len(devices) == 1:
        return devices[0]
    return ""


def open_url(device_serial: str, url: str):
    import subprocess
    subprocess.run(
        [
            "adb", "-s", device_serial, "shell",
            "am", "start", "-a", "android.intent.action.VIEW",
            "-d", url, "-p", TIKTOK_PACKAGE
        ],
        capture_output=True
    )


def adb_shell(device_serial: str, args):
    import subprocess
    subprocess.run(
        ["adb", "-s", device_serial, "shell"] + args,
        capture_output=True
    )


def input_text(device_serial: str, text: str):
    # Clear existing text: move cursor to end and long-press delete
    adb_shell(device_serial, ["input", "keyevent", "123"])
    adb_shell(device_serial, ["input", "keyevent", "--longpress", "67"])
    escaped = str(text).replace(" ", "%s")
    adb_shell(device_serial, ["input", "text", escaped])
    log(f"Inputted text: {text}")


def tap_ratio(d, x_ratio: float, y_ratio: float, delay: float = 0.3):
    w = d.info.get("displayWidth", 1080)
    h = d.info.get("displayHeight", 1920)
    x = int(x_ratio * w)
    y = int(y_ratio * h)
    d.click(x, y)
    log(f"TAP ({x_ratio:.3f}, {y_ratio:.3f}) -> ({x}, {y})")
    time.sleep(delay)


def random_swipe(d, count: int):
    w = d.info.get("displayWidth", 1080)
    h = d.info.get("displayHeight", 1920)
    for _ in range(count):
        start_x = random.randint(int(w * 0.2), int(w * 0.8))
        start_y = random.randint(int(h * 0.65), int(h * 0.85))
        end_x = random.randint(int(w * 0.2), int(w * 0.8))
        end_y = random.randint(int(h * 0.15), int(h * 0.35))
        d.swipe(start_x, start_y, end_x, end_y, duration=0.18)
        log(f"Swipe: ({start_x},{start_y}) -> ({end_x},{end_y})")
        time.sleep(3)


def random_name() -> str:
    words = [
        "minh", "hoang", "thanh", "linh", "nam", "hai", "khanh",
        "huy", "an", "phuc", "tu", "bao", "viet", "trung", "son",
        "lan", "mai", "hoa", "my", "ngoc"
    ]
    count = random.randint(3, 5)
    return " ".join(random.choice(words) for _ in range(count))


def random_phone() -> str:
    prefixes = [
        "96", "97", "98", "86", "32", "33", "34", "35", "36", "37", "38", "39",
        "90", "93", "89", "70", "76", "77", "78", "79",
        "91", "94", "88", "81", "82", "83", "84", "85",
    ]
    prefix = random.choice(prefixes)
    tail = "".join(str(random.randint(0, 9)) for _ in range(7))
    return prefix + tail


def random_address(min_words: int = 20) -> str:
    words = [
        "so", "nha", "duong", "ngo", "hem", "khu", "pho", "to",
        "thon", "ap", "xa", "phuong", "quan", "huyen", "tinh",
        "cho", "gan", "truoc", "sau", "ben", "cach", "ganh",
        "truong", "hoc", "benxe", "cong", "hoa", "tan", "phu",
        "dong", "nai", "thanh", "long", "buu", "son", "minh",
        "tien", "binh", "an", "phat", "loc", "yen"
    ]
    count = max(min_words, random.randint(min_words, min_words + 5))
    return " ".join(random.choice(words) for _ in range(count))


def main():
    serial = auto_detect_device_serial()
    if not serial:
        serial = input("Device serial (adb -s ...): ").strip()
        if not serial:
            log("Missing device serial.")
            return

    d = u2.connect(serial)
    log(f"Connected: {serial}")

    # Open link
    links = [
        "https://vt.tiktok.com/ZS91f13uCsfnd-WGnqb/",
        "https://vt.tiktok.com/ZS91fJYpjTWFM-axQ9h/",
        "https://vt.tiktok.com/ZS91fJ6aCt1aT-VTjhN/",
    ]
    link = random.choice(links)
    log(f"Opening link: {link}")
    open_url(serial, link)
    time.sleep(7.5)

    # Tap buy
    buy_coords = [
        (0.671, 0.902),
        (0.577, 0.902),
        (0.889, 0.895),
        (0.664, 0.915),
    ]
    tap_ratio(d, *random.choice(buy_coords))

    # Wait for Order Submit screen
    time.sleep(0.6)
    log("Waiting for Order Submit screen...")
    start = time.time()
    while time.time() - start < 20:
        if d(resourceId="com.zhiliaoapp.musically:id/a5c").exists:
            log("Order Submit detected.")
            break
        time.sleep(0.5)

    # Tap add address entry point
    tap_ratio(d, 0.466, 0.149)
    time.sleep(0.5)

    # Input name
    tap_ratio(d, 0.308, 0.332)
    time.sleep(0.4)
    tap_ratio(d, 0.919, 0.335)
    time.sleep(0.4)
    input_text(serial, random_name())
    time.sleep(0.6)

    # Phone number
    tap_ratio(d, 0.359, 0.439)
    time.sleep(0.4)
    input_text(serial, random_phone())
    time.sleep(0.5)
    tap_ratio(d, 0.238, 0.962)
    time.sleep(0.6)

    # Strong long swipe
    w = d.info.get("displayWidth", 1080)
    h = d.info.get("displayHeight", 1920)
    start_x = int(w * 0.58)
    start_y = int(h * 0.76)
    end_x = start_x
    end_y = int(h * 0.2)
    d.swipe(start_x, start_y, end_x, end_y, duration=0.2)
    log(f"Swipe: ({start_x},{start_y}) -> ({end_x},{end_y})")
    time.sleep(0.6)

    # Address field
    tap_ratio(d, 0.553, 0.534)
    time.sleep(0.4)
    input_text(serial, "Phu Dien, Tan Phu, Dong Nai")
    time.sleep(2.0)
    tap_ratio(d, 0.338, 0.348)
    time.sleep(0.4)
    tap_ratio(d, 0.922, 0.283)
    time.sleep(0.4)
    input_text(serial, random_address(min_words=20))
    time.sleep(0.6)

    # Back and save
    tap_ratio(d, 0.238, 0.969)
    time.sleep(0.5)
    tap_ratio(d, 0.503, 0.903)
    time.sleep(1)

    log("Done. Pausing here.")
    while True:
        time.sleep(60)


if __name__ == "__main__":
    main()
