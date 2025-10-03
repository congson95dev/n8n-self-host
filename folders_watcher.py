import os
import time
import threading
import requests
import subprocess
from watchfiles import watch, Change

# Đọc biến môi trường
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
folders_env = os.getenv("FOLDERS_TO_WATCH")

if not WEBHOOK_URL:
    raise RuntimeError("WEBHOOK_URL environment variable is not set")

if not folders_env:
    raise RuntimeError("FOLDERS_TO_WATCH environment variable is not set")

# Ví dụ FOLDERS_TO_WATCH = "/tmp/downloads,/tmp/combine-video,/tmp/folder3"
folders = [fld.strip() for fld in folders_env.split(",") if fld.strip()]

if not folders:
    raise RuntimeError("No valid folder paths parsed from FOLDERS_TO_WATCH")

# Các tham số cho kiểm tra ổn định file
CHECK_INTERVAL = float(os.getenv("CHECK_INTERVAL", "0.5"))
STABLE_CHECKS = int(os.getenv("STABLE_CHECKS", "3"))
TIMEOUT = float(os.getenv("TIMEOUT", "60.0"))

def wait_for_file_complete(path: str, timeout: float = TIMEOUT) -> bool:
    start = time.time()
    last_size = -1
    stable_count = 0
    while True:
        try:
            size = os.path.getsize(path)
        except OSError:
            return False
        if size == last_size:
            stable_count += 1
        else:
            stable_count = 0
            last_size = size
        if stable_count >= STABLE_CHECKS:
            return True
        if time.time() - start > timeout:
            return False
        time.sleep(CHECK_INTERVAL)

def get_video_duration(path: str) -> float | None:
    """Dùng ffprobe để lấy duration video (giây)."""
    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                path
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True
        )
        duration_str = result.stdout.strip()
        return float(duration_str) if duration_str else None
    except Exception as e:
        print(f"[!] Error getting duration for {path}: {e}", flush=True)
        return None

def send_webhook(path: str):
    folder_path = os.path.dirname(path)           # Lấy thư mục chứa file
    file_name = os.path.basename(path)            # Tên file
    _, file_ext = os.path.splitext(file_name)     # Lấy extension (kèm dấu .)

    duration = None
    if file_ext.lower() in [".mp4", ".mov", ".mkv", ".avi", ".webm", ".flv"]:
        duration = get_video_duration(path)

    data = {
        "file_path": path,        # full path
        "file_name": file_name,   # chỉ tên file
        "folder_path": folder_path, # thư mục chứa file
        "extension": file_ext,    # phần mở rộng file
        "duration": duration      # thời lượng video (giây, float)
    }
    try:
        resp = requests.post(WEBHOOK_URL, json=data, timeout=10)
        resp.raise_for_status()
        print(f"[+] Webhook sent: {path} => {resp.status_code}", flush=True)
    except Exception as e:
        print(f"[!] Error sending webhook for {path}: {e}", flush=True)


def handle_added(path: str):
    if wait_for_file_complete(path):
        send_webhook(path)
    else:
        print(f"[!] Skipped unstable file: {path}")

def main():
    def filter_added(change: Change, path: str) -> bool:
        return change == Change.added

    print(f"Watcher starting. Watching folders: {folders}")
    print(f"Webhook URL: {WEBHOOK_URL}")

    for changes in watch(*folders, watch_filter=filter_added):
        for change, path in changes:
            print("Detected new file:", path)
            t = threading.Thread(target=handle_added, args=(path,))
            t.daemon = True
            t.start()

if __name__ == "__main__":
    main()
