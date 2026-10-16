FROM ubuntu:24.04
RUN apt-get update && apt-get install -y --no-install-recommends \
    bats curl python3 shellcheck unzip xz-utils util-linux ca-certificates \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY . .
RUN useradd --create-home tester && chown -R tester /app
USER tester
CMD ["bats", "tests/"]
