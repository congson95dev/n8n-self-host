FROM n8nio/n8n:1.123.11

USER root

# Cài Python3, curl, yt-dlp
RUN apk update && \
    apk add --no-cache python3 py3-pip curl ffmpeg && \
    curl -L https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp \
      -o /usr/local/bin/yt-dlp && \
    chmod +x /usr/local/bin/yt-dlp

USER node
