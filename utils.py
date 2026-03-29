import os
import logging
import asyncio
import subprocess
import time


YYS_PACKAGE = "com.netease.onmyoji.wyzymnqsd_cps"


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


# Try to connect adb and check whether target device is online.
async def get_adb_devices(port=16384, host="127.0.0.1", timeout=90, interval=2):
    target = f"{host}:{port}"
    deadline = time.monotonic() + timeout

    while time.monotonic() < deadline:
        try:
            connect_proc = subprocess.run(
                ["adb", "connect", target],
                capture_output=True,
                text=True,
                check=False,
            )
            output = (connect_proc.stdout or "") + (connect_proc.stderr or "")
            if output.strip():
                logging.info(f"[INFO] adb connect {target}: {output.strip()}")

            devices_proc = subprocess.run(
                ["adb", "devices"],
                capture_output=True,
                text=True,
                check=False,
            )
            lines = devices_proc.stdout.splitlines()
            if any(line.startswith(target) and "\tdevice" in line for line in lines):
                return True
        except FileNotFoundError:
            logging.error("[ERROR] adb not found. Install Android platform-tools and add adb to PATH")
            return False
        except Exception as e:
            logging.error(f"[ERROR] adb connect failed: {e}")

        await asyncio.sleep(interval)

    return False


# Open Onmyoji in emulator after adb connection is ready.
def open_yys(port=16384, host="127.0.0.1", timeout=60):
    target = f"{host}:{port}"

    connected = asyncio.run(get_adb_devices(port=port, host=host, timeout=timeout, interval=2))
    if not connected:
        logging.error("[ERROR] ====== adb not ready, cannot launch Onmyoji ======")
        return False

    proc = subprocess.run(
        [
            "adb",
            "-s",
            target,
            "shell",
            "monkey",
            "-p",
            YYS_PACKAGE,
            "-c",
            "android.intent.category.LAUNCHER",
            "1",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    if proc.returncode == 0:
        logging.info(f"[INFO] ====== Onmyoji launch command sent: {YYS_PACKAGE} ======")
        return True

    err = (proc.stderr or proc.stdout or "").strip()
    logging.error(f"[ERROR] ====== failed to launch Onmyoji: {err} ======")
    return False


def vector():
    pass


def check_abnormal():
    pass


def check_breakthrough():
    pass


def restart():
    pass