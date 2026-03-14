FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        git \
        ffmpeg \
        espeak \
        libespeak1 \
        libespeak-dev \
        python3 \
        python3-dev \
        python3-pip \
        build-essential && \
    rm -rf /var/lib/apt/lists/*

# Install Node.js 20.x for n8n
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get update && \
    apt-get install -y nodejs && \
    rm -rf /var/lib/apt/lists/*

# Install n8n
RUN npm install -g n8n@1.123.11

# Install yt-dlp
RUN curl -L https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp \
    -o /usr/local/bin/yt-dlp && \
    chmod +x /usr/local/bin/yt-dlp

# Install Python toolchain compatible with aeneas
RUN python3 -m pip install --upgrade \
    pip==23.2.1 \
    setuptools==59.8.0 \
    wheel==0.38.4

# numpy phải cài trước aeneas
RUN pip3 install numpy==1.23.5

# install aeneas
RUN pip3 install --no-build-isolation aeneas

# create node user
RUN useradd -m -u 1000 node
USER node

WORKDIR /home/node
VOLUME ["/home/node/.n8n"]

EXPOSE 5678
CMD ["n8n"]