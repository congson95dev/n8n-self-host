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

