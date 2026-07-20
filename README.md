# n8n self-host (4 workers)

This stack runs:
- `postgres`
- `redis`
- `caddy`
- `n8n` (main/webhook/editor)
- `n8n-worker-1..4` (4 fixed workers, no `--scale` needed)

## 1) Required `.env`

Your `docker-compose.yml` currently reads these variables:

```env
DEPLOY_FOLDER=/home/n8n-deploy
DOMAIN_NAME=your-domain.com
GENERIC_TIMEZONE=Asia/Ho_Chi_Minh
DOCKER_LOG_MAX_SIZE=50m
DOCKER_LOG_MAX_FILE=3
N8N_ENCRYPTION_KEY=put-your-existing-key-here
```

Important notes:
- `N8N_ENCRYPTION_KEY` is required and must be the same for `n8n` and all workers.
- If you already have old n8n data, reuse the same `N8N_ENCRYPTION_KEY`.
- `DEPLOY_FOLDER` must match the host path used by caddy and local file mounts.

### Recover existing `N8N_ENCRYPTION_KEY` from current container

If `docker exec -it n8n_docker printenv N8N_ENCRYPTION_KEY` returns empty, read it from n8n config:

```bash
docker exec -it n8n_docker sh -lc "cat /home/node/.n8n/config | grep encryptionKey"
```

Example output:

```text
"encryptionKey": "i+s4Kgdhc9GJLdOgaQbcQWTfMJx0Z6Ld"
```

Then put the value into `.env`:

```env
N8N_ENCRYPTION_KEY=i+s4Kgdhc9GJLdOgaQbcQWTfMJx0Z6Ld
```

Fallback (read from docker volume directly):

```bash
docker run --rm -v n8n-data:/data alpine sh -lc "cat /data/config | grep encryptionKey"
```

## 2) Start services

```bash
docker compose up -d --build
```

No extra flag is needed. This automatically starts all 4 worker services.

## 3) Verify workers are running

```bash
docker compose ps
```

You should see:
- `n8n-worker-1`
- `n8n-worker-2`
- `n8n-worker-3`
- `n8n-worker-4`

Optional check logs:

```bash
docker compose logs -f n8n-worker-1
```

## 4) Usual operations

Restart everything:

```bash
docker compose restart
```

Stop everything:

```bash
docker compose down
```

Update images and recreate containers:

```bash
docker compose pull
docker compose up -d --build
```

## 5) Access

- n8n is exposed through caddy using `DOMAIN_NAME`.
- Webhook base URL is `https://${DOMAIN_NAME}` (from compose env).
