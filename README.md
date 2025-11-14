# Setup
## API List and Their Purpose

## API v1
- **Purpose:** Detects parts of videos that are longer than 2 seconds.
- **Limitation:** Does not work with videos shorter than 2 seconds.

## API v2
- **Purpose:** Detects video bars using a fallback mechanism in case standard detection fails, particularly useful for videos less than 2 seconds.

## API v3
- **Purpose:** Detects each part of a video when it contains a dynamic bar (e.g., input/input_dynamic_bar.mp4). This version works well for separating video parts.
- **Issue:** The detected `y_top` is not correct, and `y_bottom` may also be incorrect.

## API v4
- **Purpose:** Serves as a copy of API v1 but is designed to work properly for videos shorter than 2 seconds.
- **Issue:** Currently does not detect correctly.

Run the below command:
```
mkdir .n8n
chown -R 1000:1000 .n8n
docker compose up -d
```

Access the n8n web interface at http://localhost:5678

Update n8n to newest version:
```
docker compose pull
docker compose up -d
```

Manual test:
```
python3 -m venv venv
source venv/bin/activate
pip install opencv-python Flask
export FLASK_APP=api.py && flask run watchfiles requests
```

Detect video bars:
```
http:127.0.0.1/detect/{file-path}/input.mp4
```

Folder watcher:
```
python3 folders_watcher.py
```
