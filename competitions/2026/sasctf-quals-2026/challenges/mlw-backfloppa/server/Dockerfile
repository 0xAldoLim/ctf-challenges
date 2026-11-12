FROM alpine:3.20

RUN addgroup -S app && adduser -S -G app -h /home/app -s /bin/sh app

COPY flag.txt /flag
RUN chmod 0444 /flag && chown root:root /flag

USER app
WORKDIR /home/app

CMD ["sleep", "infinity"]
