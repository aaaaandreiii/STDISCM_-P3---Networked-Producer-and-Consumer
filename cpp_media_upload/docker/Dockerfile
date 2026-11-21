FROM ubuntu:noble-20261110.1 AS runtime

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libgrpc++1.51t64 libprotobuf32t64 libsqlite3-0 libssl3t64 libstdc++6 \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 10001 mediadock \
    && useradd --uid 10001 --gid 10001 --no-create-home mediadock

FROM runtime AS consumer-runtime

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ffmpeg libdrogon1t64 \
    && rm -rf /var/lib/apt/lists/*

FROM consumer-runtime AS builder

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        cmake g++ ninja-build pkg-config \
        libbrotli-dev libdrogon-dev libgrpc++-dev libhiredis-dev libjsoncpp-dev \
        libmariadb-dev libpq-dev libprotobuf-dev libsqlite3-dev libssl-dev \
        libyaml-cpp-dev protobuf-compiler protobuf-compiler-grpc uuid-dev zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /src
COPY CMakeLists.txt .
COPY proto/ proto/
COPY src/ src/
COPY tests/ tests/

# Debug keeps the baseline C++ test assertions active.
RUN cmake -S . -B /build -G Ninja -DCMAKE_BUILD_TYPE=Debug \
        -DBUILD_FULL_APP=ON -DBUILD_TESTING=ON \
    && cmake --build /build --parallel 1 \
    && ffmpeg -version >/dev/null \
    && ffprobe -version >/dev/null \
    && ctest --test-dir /build --output-on-failure --no-tests=error \
        --parallel 1 --output-junit /build/ctest.xml \
    && ! grep -q '<skipped' /build/ctest.xml \
    && strip --strip-debug /build/media_producer /build/media_consumer

FROM runtime AS producer

ARG IMAGE_REVISION
LABEL org.opencontainers.image.revision="${IMAGE_REVISION}"
WORKDIR /opt/mediadock
COPY --from=builder /build/media_producer /usr/local/bin/media_producer
USER 10001:10001
ENTRYPOINT ["/usr/local/bin/media_producer"]

FROM consumer-runtime AS consumer

ARG IMAGE_REVISION
LABEL org.opencontainers.image.revision="${IMAGE_REVISION}"
WORKDIR /opt/mediadock
COPY --from=builder /build/media_consumer /usr/local/bin/media_consumer
COPY web/ /opt/mediadock/web/
# Docker copies the seeded directory into each new named volume.
RUN install -d -m 0750 -o 10001 -g 10001 /data /data/incoming /data/uploads /data/previews
USER 10001:10001
EXPOSE 50051 8080
ENTRYPOINT ["/usr/local/bin/media_consumer"]
