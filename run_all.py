import subprocess
import sys
import os

SCRIPTS = [
    "elnuevodia.py",
    "elvocero.py",
    "laperladelsur.py",
    "claridad.py",
    "metro.py",
    "newsismybusiness.py",
    "noticel.py",
    "primerahora.py",
    "sincimillas.py",
    "telemundopr.py",
    "wapatv.py",
    "twitter.py",
    "update_twitter.py",
]

LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)

failed_scripts = []

for script in SCRIPTS:
    print(f"\n[OK] Running {script}")
    log_file = f"{LOG_DIR}/{script.replace('.py', '')}.log"

    with open(log_file, "w", encoding="utf-8") as f:
        process = subprocess.Popen(
            [sys.executable, script],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )

        # Read line by line
        for line in process.stdout:
            print(line, end="")  # live output to console
            f.write(line)  # write to log file

        process.wait()

        if process.returncode != 0:
            failed_scripts.append(script)
            print(f"[FAIL] {script} (see {log_file})")
        else:
            print(f"[OK] {script} completed")

# ===== Summary =====
print("\n====================")
print("SCRAPE SUMMARY")
print("====================")

if failed_scripts:
    print("[FAIL] Failed scripts:")
    for s in failed_scripts:
        print(f"  - {s}")
else:
    print("[OK] All scripts ran successfully")
