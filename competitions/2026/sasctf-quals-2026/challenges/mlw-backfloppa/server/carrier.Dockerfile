FROM golang:1.23-alpine AS build

RUN apk add --no-cache perl
WORKDIR /src

COPY go.mod go.sum ./
RUN go mod download

COPY . .
RUN perl -0pi -e 's/(crictlVersion\s+= "crictl version v1\.31\.1"\n)/$1\tshellPath        = "\/usr\/local\/bin\/runtime-session"\n/' main.go \
 && perl -0pi -e 's/exec\.CommandContext\(ctx, "\/bin\/sh"\)/exec.CommandContext(ctx, shellPath)/' main.go \
 && GOOS=linux GOARCH=amd64 go build -trimpath -ldflags="-s -w" -o /out/ebpf-backdoor-server .

FROM alpine:3.20

RUN apk add --no-cache ca-certificates docker-cli iproute2

COPY runtime-session /usr/local/bin/runtime-session
COPY carrier-entrypoint /usr/local/bin/carrier-entrypoint
COPY --from=build /out/ebpf-backdoor-server /usr/local/bin/ebpf-backdoor-server

RUN chmod 0755 /usr/local/bin/runtime-session /usr/local/bin/carrier-entrypoint /usr/local/bin/ebpf-backdoor-server

ENTRYPOINT ["/usr/local/bin/carrier-entrypoint"]
