# Setup
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
export FLASK_APP=api.py && flask run
http:127.0.0.1/detect/{file-path}/input.mp4
```