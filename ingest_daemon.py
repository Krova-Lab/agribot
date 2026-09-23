#!/usr/bin/env python3
import time
import os
import sys
from datetime import datetime
import subprocess

DROPZONE = os.path.expanduser("~/agribot/rag_dropzone")
INGEST_SCRIPT = os.path.expanduser("~/agribot/ingest_files.py")
PYTHON_BIN = sys.executable

def is_daytime() -> bool:
    """Treat 06:00-22:00 as the high-activity period."""
    now = datetime.now()
    return 6 <= now.hour < 22

def apply_priority(daytime: bool):
    """Adjust the current process nice level according to the cycle."""
    try:
        current_pid = os.getpid()
        target_nice = 19 if daytime else 0
        os.nice(target_nice - os.nice(0))
    except Exception:
        pass

def has_pending_files() -> bool:
    if not os.path.exists(DROPZONE):
        return False
    files = [f for f in os.listdir(DROPZONE) if not f.startswith('.')]
    return len(files) > 0

def run():
    print("✓ Starting adaptive ingestion daemon (day: low priority / night: normal)...")
    while True:
        daytime = is_daytime()
        apply_priority(daytime)

        if has_pending_files():
            mode_str = "JOUR (Low-priority)" if daytime else "NUIT (Boosted)"
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Fichiers détectés. Lancement mode {mode_str}...")
            
            # ionice prefix: idle during the day, normal at night
            io_cmd = ["ionice", "-c", "3"] if daytime else ["ionice", "-c", "2", "-n", "4"]
            cmd = io_cmd + [PYTHON_BIN, INGEST_SCRIPT]
            
            subprocess.run(cmd)
            
            # Pause between batches: longer daytime delay to preserve API quotas
            sleep_time = 30 if daytime else 5
        else:
            # Passive directory monitoring
            sleep_time = 15 if daytime else 5

        time.sleep(sleep_time)

if __name__ == "__main__":
    run()
