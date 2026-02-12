FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get upgrade -y && \
    apt-get install -y \
    make git zlib1g-dev libssl-dev gperf cmake clang-14 \
    libc++-14-dev libc++abi-14-dev ca-certificates && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

RUN git clone --recursive https://github.com/tdlib/telegram-bot-api.git

WORKDIR /app/telegram-bot-api

RUN rm -rf build && mkdir build
WORKDIR /app/telegram-bot-api/build

RUN CXXFLAGS="-stdlib=libc++" \
    CC=/usr/bin/clang-14 \
    CXX=/usr/bin/clang++-14 \
    cmake -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX:PATH=.. .. && \
    cmake --build . --target install

WORKDIR /app/telegram-bot-api/bin

EXPOSE 8081

CMD ["./telegram-bot-api"]