FROM coredns/coredns:1.12.1 AS coredns-bin

FROM alpine:latest

RUN apk add --no-cache iproute2

COPY --from=coredns-bin /coredns /coredns
COPY Corefile /etc/coredns/Corefile
COPY zones/ /etc/coredns/zones/

EXPOSE 53/udp 53/tcp

ENTRYPOINT ["/coredns"]
CMD ["-conf", "/etc/coredns/Corefile"]
