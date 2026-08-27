#!/usr/bin/env python3
"""
Master Runner Script with Exponential Backoff and Crash Loop Prevention.
Runs both guide_bot.py and main.py concurrently.
"""

import subprocess
import sys
import time
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("runner")

def run_services():
    processes = {}
    scripts = ["guide_bot.py", "main.py"]
    backoff = {script: 1 for script in scripts}
    max_backoff = 60

    logger.info("Memulakan perkhidmatan TGBioUpdater...")

    for script in scripts:
        processes[script] = subprocess.Popen([sys.executable, script])

    try:
        while True:
            for script in scripts:
                proc = processes[script]
                retcode = proc.poll()
                if retcode is not None:
                    logger.warning("%s telah terhenti dengan kod: %s. Melakukan restart dalam %ss...", script, retcode, backoff[script])
                    time.sleep(backoff[script])
                    processes[script] = subprocess.Popen([sys.executable, script])
                    backoff[script] = min(backoff[script] * 2, max_backoff)
                else:
                    backoff[script] = 1
            time.sleep(5)
    except KeyboardInterrupt:
        logger.info("Menghentikan semua perkhidmatan...")
        for proc in processes.values():
            proc.terminate()
        sys.exit(0)

if __name__ == "__main__":
    run_services()
