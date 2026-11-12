FROM gcc:15.2.0 AS builder

WORKDIR /build
COPY readflag.c .
RUN gcc -O2 -o readflag readflag.c

FROM python:3.14.5-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential curl libpq-dev \
    && rm -rf /var/lib/apt/lists/*
RUN curl -sSL https://install.python-poetry.org | python3 -

RUN useradd -m -s /bin/sh cloud \
    && mkdir -p /home/cloud/storages /home/cloud/runtime /usr/local/libexec

ENV PATH="/root/.local/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHON_DISABLE_REMOTE_DEBUG=1
WORKDIR /home/cloud

COPY pyproject.toml ./

RUN poetry config virtualenvs.create false
RUN poetry install --no-root


COPY entry.sh .
COPY src .

COPY --from=builder /build/readflag /readflag
RUN chmod 4111 /readflag \
    && chmod +x ./entry.sh \
    && chown -R cloud:cloud /home/cloud \
    && chmod 755 /home/cloud

CMD ["./entry.sh", "api"]
