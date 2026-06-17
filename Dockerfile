FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        git \
        ffmpeg \
        python3 \
        python3-dev \
        python3-pip \
        build-essential && \
    rm -rf /var/lib/apt/lists/*

# Install Node.js 20.x for n8n
RUN curl -fsSL https://deb.nodesource.com/setup_22.x | bash - && \
    apt-get update && \
    apt-get install -y nodejs && \
    rm -rf /var/lib/apt/lists/*

# Install n8n version 1.x
RUN npm install -g n8n@^1

# Install yt-dlp
RUN curl -L https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp \
    -o /usr/local/bin/yt-dlp && \
    chmod +x /usr/local/bin/yt-dlp

# Install openai-whisper and its dependencies
RUN python3 -m pip install --upgrade pip setuptools wheel && \
    pip3 install torch torchvision torchaudio && \
    pip3 install openai-whisper

RUN useradd -m -u 1000 node
USER node

WORKDIR /home/node
VOLUME ["/home/node/.n8n"]

EXPOSE 5678
CMD ["n8n"]