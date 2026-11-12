FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

WORKDIR /app

COPY app/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./
COPY qemu-system-riscv64.7z /tmp/qemu-system-riscv64.7z
COPY entrypoint.sh /entrypoint.sh
RUN apt-get update \
 && apt-get install -y --no-install-recommends p7zip-full \
 && 7z x -y -o/opt/gatekeeper /tmp/qemu-system-riscv64.7z \
 && rm /tmp/qemu-system-riscv64.7z \
 && apt-get purge -y --auto-remove p7zip-full \
 && rm -rf /var/lib/apt/lists/* \
 && chmod +x /opt/gatekeeper/qemu-system-riscv64 /entrypoint.sh

EXPOSE 2048
ENTRYPOINT ["/entrypoint.sh"]
