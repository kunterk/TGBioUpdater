import os
import subprocess
import sys

def main():
    session_string = os.environ.get("SESSION_STRING")
    
    if not session_string:
        print("[INFO] SESSION_STRING tiada. Scrobbler tidak dijalankan.")
        sys.exit(0)
        
    print("[INFO] Memulakan Bio Scrobbler (main.py)...")
    p = subprocess.Popen([sys.executable, "main.py"])
    p.wait()

if __name__ == "__main__":
    main()
