# Dùng image CUDA base để hỗ trợ GPU
FROM nvidia/cuda:12.2.0-devel-ubuntu22.04

# Cài các công cụ hệ thống, Node & Python
USER root
ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
      build-essential \
      git \
      wget \
      curl \
      ca-certificates \
      pkg-config \
      yasm \
      nasm \
      libnuma-dev \
      libx264-dev \
      libx265-dev \
      libvpx-dev \
      libfdk-aac-dev \
      libopus-dev \
      libmp3lame-dev \
      libass-dev \
      libfreetype6-dev \
      python3 \
      python3-pip \
      gnupg \
      npm \
    && rm -rf /var/lib/apt/lists/*

RUN apt-get remove -y libnode-dev nodejs npm || true
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs

# Cài nv-codec-headers để FFmpeg biết NVENC / NVDEC
RUN git clone https://git.videolan.org/git/ffmpeg/nv-codec-headers.git /tmp/nv-codec-headers \
    && cd /tmp/nv-codec-headers \
    && make install \
    && rm -rf /tmp/nv-codec-headers

# Build FFmpeg từ source với hỗ trợ GPU
RUN mkdir -p /tmp/ffmpeg_build && cd /tmp \
    && wget https://ffmpeg.org/releases/ffmpeg-snapshot.tar.bz2 \
    && tar xjf ffmpeg-snapshot.tar.bz2 \
    && cd ffmpeg \
    && ./configure \
         --prefix=/usr/local/ffmpeg \
         --extra-cflags="-I/usr/local/cuda/include" \
         --extra-ldflags="-L/usr/local/cuda/lib64" \
         --enable-cuda \
         --enable-cuvid \
         --enable-nvenc \
         --enable-nvdec \
         --enable-libnpp \
         --enable-gpl \
         --enable-nonfree \
         --enable-libx264 \
         --enable-libx265 \
         --enable-libvpx \
         --enable-libfdk-aac \
         --enable-libopus \
         --enable-libmp3lame \
         --enable-libass \
         --enable-libfreetype \
         --disable-debug \
    && make -j"$(nproc)" \
    && make install \
    && rm -rf /tmp/ffmpeg_build /tmp/ffmpeg-snapshot*

# Đặt PATH để dùng ffmpeg mới
ENV PATH="/usr/local/ffmpeg/bin:${PATH}"

# Cài yt-dlp
RUN curl -L https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp \
      -o /usr/local/bin/yt-dlp \
    && chmod +x /usr/local/bin/yt-dlp

# Cài n8n (qua npm)
RUN npm install -g n8n@latest

# Tạo user node (giống image gốc)
RUN useradd --system --create-home --shell /bin/bash node \
    && mkdir -p /home/node/.n8n \
    && chown -R node:node /home/node

USER node

EXPOSE 5678

ENTRYPOINT ["n8n"]
