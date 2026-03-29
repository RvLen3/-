from utils import *

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    start_emulator()
    start_screenshot_loop(interval=2)
    try:
        open_yys()
    except Exception as e:
        logging.error(f"[ERROR] An error occurred: {e}")
        logging.info("[INFO] Attempting to restart the onmyoji process")
        pass
