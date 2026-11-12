CC ?= gcc
CFLAGS := -Os -nostartfiles -no-pie -fno-pic -fno-stack-protector \
	-fno-builtin -fno-asynchronous-unwind-tables -fno-unwind-tables -Wall -Wextra
LDFLAGS := -Wl,-e,_start -Wl,--build-id=none -Wl,--no-as-needed -s

.PHONY: all clean

all: agent rev_agent

agent: agent.c
	$(CC) $(CFLAGS) $(LDFLAGS) -o $@ $< -lc

rev_agent: agent.c
	$(CC) $(CFLAGS) -DREVERSE $(LDFLAGS) -o $@ $< -lc

clean:
	rm -f agent rev_agent
