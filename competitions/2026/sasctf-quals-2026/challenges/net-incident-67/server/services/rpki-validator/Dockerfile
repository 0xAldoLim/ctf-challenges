FROM golang:1.25-alpine AS builder

RUN apk add --no-cache git && \
    go install github.com/bgp/stayrtr/cmd/stayrtr@latest

FROM alpine:latest

COPY --from=builder /go/bin/stayrtr /usr/local/bin/stayrtr
COPY roas.json /data/roas.json

EXPOSE 3323

ENTRYPOINT ["stayrtr"]
CMD ["-cache", "/data/roas.json", "-bind", ":3323", "-checktime=false"]
