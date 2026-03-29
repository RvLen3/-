import os
import logging
import asyncio
import subprocess
import time
import shutil
import threading
from pathlib import Path


YYS_PACKAGE = "com.netease.onmyoji.wyzymnqsd_cps"
ADB_CANDIDATES = [
    r"D:/Program Files/Netease/MuMu/nx_main/adb.exe",
    r"D:/Program Files/Netease/MuMu/nx_device/12.0/shell/adb.exe",
]
LIVE_SCREENSHOT_PATH = "runtime/latest_screen.png"
_screenshot_thread = None
_screenshot_stop_event = threading.Event()


def _resolve_adb():
    adb_in_path = shutil.which("adb")
    if adb_in_path:
        return adb_in_path

    for adb_path in ADB_CANDIDATES:
        if os.path.exists(adb_path):
            return adb_path

    return None


def _run_adb(args, capture_output=True):
    adb_cmd = _resolve_adb()
    if not adb_cmd:
        raise FileNotFoundError("adb not found")

    return subprocess.run(
        [adb_cmd, *args],
        capture_output=capture_output,
        text=True if capture_output else False,
        encoding="utf-8" if capture_output else None,
        errors="replace" if capture_output else None,
        check=False,
    )


# Start MuMu manager process and wait for adb-ready device.
def start_emulator():
    os.startfile(r"D:/Program Files/Netease/MuMu/nx_main/MuMuNxMain.exe")
    logging.info("[INFO] ====== MuMu launcher started ======")
    logging.info("[INFO] ====== waiting for Android device to be adb-ready ======")

    connected = asyncio.run(get_adb_devices())
    if connected:
        logging.info("[INFO] ====== adb connected, emulator is ready ======")
    else:
        logging.warning("[WARN] ====== adb connect timeout, please boot Android device in MuMu ======")


async def get_adb_devices(port=16384, host="127.0.0.1", timeout=90, interval=2):
    target = f"{host}:{port}"
    deadline = time.monotonic() + timeout
    if not _resolve_adb():
        logging.error("[ERROR] adb not found in MuMu directory or PATH")
        return False

    while time.monotonic() < deadline:
        try:
            connect_proc = _run_adb(["connect", target])
            output = (connect_proc.stdout or "") + (connect_proc.stderr or "")
            if output.strip():
                logging.info(f"[INFO] adb connect {target}: {output.strip()}")

            devices_proc = _run_adb(["devices"])
            lines = devices_proc.stdout.splitlines()
            if any(line.startswith(target) and "\tdevice" in line for line in lines):
                return True
        except FileNotFoundError:
            logging.error("[ERROR] adb executable is missing, please check MuMu install path")
            return False
        except Exception as e:
            logging.error(f"[ERROR] adb connect failed: {e}")

        await asyncio.sleep(interval)

    return False


def open_yys(port=16384, host="127.0.0.1", timeout=60):
    target = f"{host}:{port}"
    if not _resolve_adb():
        logging.error("[ERROR] ====== adb not found, cannot launch Onmyoji ======")
        return False

    connected = asyncio.run(get_adb_devices(port=port, host=host, timeout=timeout, interval=2))
    if not connected:
        logging.error("[ERROR] ====== adb not ready, cannot launch Onmyoji ======")
        return False

    proc = _run_adb(
        [
            "-s",
            target,
            "shell",
            "monkey",
            "-p",
            YYS_PACKAGE,
            "-c",
            "android.intent.category.LAUNCHER",
            "1",
        ]
    )
    launch_output = ((proc.stdout or "") + (proc.stderr or "")).strip().lower()
    if proc.returncode != 0 and "error: closed" in launch_output:
        logging.warning("[WARN] adb transport closed while launching app, reconnecting and retrying once")
        _run_adb(["connect", target])
        time.sleep(1)
        proc = _run_adb(
            [
                "-s",
                target,
                "shell",
                "monkey",
                "-p",
                YYS_PACKAGE,
                "-c",
                "android.intent.category.LAUNCHER",
                "1",
            ]
        )

    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "").strip()
        logging.error(f"[ERROR] ====== failed to launch Onmyoji: {err} ======")
        return False

    logging.info(f"[INFO] ====== Onmyoji launch command sent: {YYS_PACKAGE} ======")

    clicked = wait_and_click_login(
        port=port,
        host=host,
        template_path="imgs/login.png", 
        timeout=90,
        interval=2,
        screenshot_path=LIVE_SCREENSHOT_PATH,
    )
    if not clicked:
        logging.warning("[WARN] ====== login target not detected within timeout ======")
        return False

    return True


def take_screenshot(output_path=LIVE_SCREENSHOT_PATH, port=16384, host="127.0.0.1"):
    adb_cmd = _resolve_adb()
    target = f"{host}:{port}"
    output_file = Path(output_path)

    if not adb_cmd:
        logging.error("[ERROR] adb not found, cannot take screenshot")
        return False

    output_file.parent.mkdir(parents=True, exist_ok=True)
    with output_file.open("wb") as f:
        proc = subprocess.run(
            [adb_cmd, "-s", target, "exec-out", "screencap", "-p"],
            stdout=f,
            stderr=subprocess.PIPE,
            check=False,
        )

    if proc.returncode != 0:
        err = (proc.stderr or b"").decode("utf-8", errors="replace").strip()
        logging.error(f"[ERROR] take_screenshot failed: {err}")
        return False

    return True


def adb_tap(x, y, port=16384, host="127.0.0.1"):
    target = f"{host}:{port}"

    if not _resolve_adb():
        logging.error("[ERROR] adb not found, cannot tap")
        return False

    proc = _run_adb(["-s", target, "shell", "input", "tap", str(int(x)), str(int(y))])
    return proc.returncode == 0


def _screenshot_loop_worker(port, host, interval, screenshot_path):
    while not _screenshot_stop_event.is_set():
        take_screenshot(screenshot_path, port=port, host=host)
        _screenshot_stop_event.wait(interval)


def start_screenshot_loop(port=16384, host="127.0.0.1", interval=2, screenshot_path=LIVE_SCREENSHOT_PATH):
    global _screenshot_thread

    if _screenshot_thread and _screenshot_thread.is_alive():
        logging.info("[INFO] screenshot loop already running")
        return

    _screenshot_stop_event.clear()
    _screenshot_thread = threading.Thread(
        target=_screenshot_loop_worker,
        args=(port, host, interval, screenshot_path),
        daemon=True,
        name="adb-screenshot-loop",
    )
    _screenshot_thread.start()
    logging.info(f"[INFO] screenshot loop started: every {interval}s -> {screenshot_path}")


def stop_screenshot_loop():
    global _screenshot_thread

    _screenshot_stop_event.set()
    if _screenshot_thread and _screenshot_thread.is_alive():
        _screenshot_thread.join(timeout=2)
    _screenshot_thread = None
    logging.info("[INFO] screenshot loop stopped")


def wait_and_click_login(port=16384, host="127.0.0.1", template_path="assets/login_screen.png", timeout=90, interval=2, screenshot_path=LIVE_SCREENSHOT_PATH):
    deadline = time.monotonic() + timeout

    while time.monotonic() < deadline:
        if not take_screenshot(screenshot_path, port=port, host=host):
            time.sleep(interval)
            continue

        match = compute_location(template_path, screenshot_path)
        if match:
            x, y, score = match
            logging.info(f"[INFO] login target detected at ({x}, {y}), confidence={score:.3f}")
            if adb_tap(x, y, port=port, host=host):
                logging.info("[INFO] ====== login tapped ======")
                return True

            logging.warning("[WARN] login target detected but tap failed, retrying...")

        time.sleep(interval)

    return False


def compute_location(image1, image2):
    try:
        import cv2
    except ImportError:
        logging.error("[ERROR] OpenCV not installed. Please run: pip install opencv-python")
        return None

    def _to_bgr(img):
        if isinstance(img, str):
            return cv2.imread(img, cv2.IMREAD_COLOR)
        return img

    template = _to_bgr(image1)
    target = _to_bgr(image2)

    if template is None or target is None:
        logging.error("[ERROR] compute_location failed to load input image(s)")
        return None

    th, tw = template.shape[:2]
    hh, hw = target.shape[:2]
    if th > hh or tw > hw:
        logging.warning("[WARN] template is larger than target image")
        return None

    result = cv2.matchTemplate(target, template, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, max_loc = cv2.minMaxLoc(result)

    threshold = 0.80
    if max_val < threshold:
        return None

    x = max_loc[0] + tw // 2
    y = max_loc[1] + th // 2
    return x, y, float(max_val)


def victory():
    pass


def check_abnormal():
    pass


def check_breakthrough():
    pass


def restart():
    pass
