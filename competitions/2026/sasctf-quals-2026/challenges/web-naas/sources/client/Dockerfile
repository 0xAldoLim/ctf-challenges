FROM golang:alpine AS builder

WORKDIR /app
COPY . .

RUN go mod download
RUN go build -o nslp-cli main.go

FROM alpine:latest

COPY --from=builder /app/nslp-cli /bin
RUN mkdir /tmp/volume

ENV CONFIG_PATH=/tmp/volume/.nslp.conf

ENTRYPOINT [ "nslp-cli" ]