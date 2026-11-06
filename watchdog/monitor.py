import logging
import signal
import subprocess
import sys
import threading
from pathlib import Path

from config import (
    WATCHDOG_ENABLED,
    WATCHDOG_CHECK_INTERVAL,
    WATCHDOG_RESTART_ENABLED,
    WATCHDOG_MAX_RESTARTS,
    WATCHDOG_RESTART_DELAY,
)

from watchdog.telegram import send_telegram_sync


PROJECT_DIR = Path(__file__).resolve().parent.parent
MAIN_SCRIPT = PROJECT_DIR / "main.py"

logging.basicConfig(
    level=logging.INFO,
    format="[WATCHDOG] %(asctime)s %(levelname)s: %(message)s",
)


def notify_admin(message: str):
    """Send watchdog and emergency notifications through Telegram only."""
    logging.info("Sending Telegram admin notification...")
    try:
        telegram_ok = send_telegram_sync(message)
        logging.info("Telegram notification: %s", telegram_ok)
    except Exception as error:
        logging.error("Telegram notification error: %s", type(error).__name__)

def run_watchdog():
    if WATCHDOG_CHECK_INTERVAL < 1:
        raise ValueError("WATCHDOG_CHECK_INTERVAL must be at least 1")

    if WATCHDOG_MAX_RESTARTS < 1:
        raise ValueError("WATCHDOG_MAX_RESTARTS must be at least 1")

    if WATCHDOG_RESTART_DELAY < 0:
        raise ValueError("WATCHDOG_RESTART_DELAY cannot be negative")

    if not MAIN_SCRIPT.is_file():
        raise FileNotFoundError(MAIN_SCRIPT)

    stop_event = threading.Event()
    process = None

    def handle_stop(signum, frame):
        logging.info("Shutdown requested.")
        stop_event.set()

    signal.signal(signal.SIGINT, handle_stop)
    signal.signal(signal.SIGTERM, handle_stop)

    if not WATCHDOG_ENABLED:
        logging.info("Watchdog disabled. Starting bot without auto-restart.")

        process = subprocess.Popen(
            [sys.executable, str(MAIN_SCRIPT)],
            cwd=PROJECT_DIR,
        )

        while process.poll() is None and not stop_event.wait(
            WATCHDOG_CHECK_INTERVAL
        ):
            pass

        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()

        return 0 if stop_event.is_set() else process.returncode

    restart_count = 0

    logging.info("Watchdog started.")
    notify_admin("🟢 GroupControler-FB Watchdog started.")

    try:
        while not stop_event.is_set():
            logging.info("Starting Facebook bot...")

            process = subprocess.Popen(
                [sys.executable, str(MAIN_SCRIPT)],
                cwd=PROJECT_DIR,
            )

            logging.info("Bot PID: %s", process.pid)

            while process.poll() is None and not stop_event.wait(
                WATCHDOG_CHECK_INTERVAL
            ):
                pass

            if stop_event.is_set():
                if process.poll() is None:
                    process.terminate()

                    try:
                        process.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait()

                notify_admin("🛑 GroupControler-FB stopped manually.")
                break

            exit_code = process.returncode

            if exit_code == 0:
                logging.info("Bot exited normally.")
                notify_admin("ℹ️ Facebook bot exited normally.")
                break

            restart_count += 1

            message = (
                "🚨 Facebook bot crashed!\n"
                f"Exit code: {exit_code}\n"
                f"Restart: {restart_count}/{WATCHDOG_MAX_RESTARTS}"
            )

            logging.error(message)
            notify_admin(message)

            if not WATCHDOG_RESTART_ENABLED:
                logging.warning("Automatic restart disabled.")
                notify_admin("⛔ Automatic restart is disabled. Watchdog stopped.")
                break

            if restart_count >= WATCHDOG_MAX_RESTARTS:
                logging.critical("Maximum restart limit reached.")
                notify_admin(
                    "⛔ Watchdog stopped: maximum restart limit reached."
                )
                break

            logging.info(
                "Restarting in %s seconds...",
                WATCHDOG_RESTART_DELAY,
            )

            if stop_event.wait(WATCHDOG_RESTART_DELAY):
                notify_admin("🛑 Watchdog stopped before the next restart.")
                break

    finally:
        logging.info("Watchdog process closed.")


if __name__ == "__main__":
    run_watchdog()
