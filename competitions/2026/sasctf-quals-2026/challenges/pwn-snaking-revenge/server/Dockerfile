FROM ubuntu:24.04@sha256:786a8b558f7be160c6c8c4a54f9a57274f3b4fb1491cf65146521ae77ff1dc54 AS ubuntu

RUN apt-get update && apt-get install -y \
    socat python3 python3-pip openjdk-21-jdk \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

RUN pip3 install pyjnius --break-system-packages

RUN useradd -M -u 1001 -s /usr/sbin/nologin ctf

WORKDIR /app

COPY main.py /app/main.py
COPY wrapper.py /app/wrapper.py
COPY restrict.policy /app/restrict.policy
COPY jnius.security /app/jnius.security
COPY flag.txt /app/flag.txt
COPY run.sh /app/run

RUN chown -R root:root /app \
    && chmod 444  /app/flag.txt /app/main.py /app/wrapper.py \
                  /app/restrict.policy /app/jnius.security \
    && chmod 555  /app/run

USER ctf

CMD ["/app/run"]
