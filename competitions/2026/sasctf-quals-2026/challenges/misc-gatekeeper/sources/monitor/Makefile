# Build the Gatekeeper M-mode monitor blob (baked into QEMU).

CROSS_COMPILE ?= riscv64-linux-gnu-
CC      := $(CROSS_COMPILE)gcc
OBJCOPY := $(CROSS_COMPILE)objcopy
OBJDUMP := $(CROSS_COMPILE)objdump

BUILD_DIR := build
TARGET    := monitor

ARCH_FLAGS := -march=rv64im_zicsr -mabi=lp64 -mcmodel=medany \
              -static -nostdlib -nostartfiles -fno-omit-frame-pointer
# -fno-inline: keep the syscall handlers and MMIO/device helpers as real
# functions (with call boundaries and epilogues) instead of folding everything
# into trap_handler. This mirrors how a real monitor is structured.
CFLAGS     := $(ARCH_FLAGS) -O2 -fno-inline -ffreestanding -Wall -Wextra -I.
LDFLAGS    := $(ARCH_FLAGS) -T monitor.ld -Wl,--build-id=none \
              -Wl,-Map="$(BUILD_DIR)/$(TARGET).map"

OBJS := $(BUILD_DIR)/start.o $(BUILD_DIR)/monitor.o

.PHONY: all blob disasm clean

all: $(BUILD_DIR)/$(TARGET).bin

$(BUILD_DIR):
	mkdir -p $@

$(BUILD_DIR)/%.o: %.c | $(BUILD_DIR)
	$(CC) $(CFLAGS) -c $< -o $@

$(BUILD_DIR)/%.o: %.S | $(BUILD_DIR)
	$(CC) $(CFLAGS) -c $< -o $@

$(BUILD_DIR)/$(TARGET).elf: $(OBJS) monitor.ld
	$(CC) $(LDFLAGS) $(OBJS) -o $@

$(BUILD_DIR)/$(TARGET).bin: $(BUILD_DIR)/$(TARGET).elf
	$(OBJCOPY) -O binary $< $@

# Generate the C array baked into QEMU: build_monitor_bin[] / _len.
blob: $(BUILD_DIR)/$(TARGET).bin
	xxd -i $(BUILD_DIR)/$(TARGET).bin > $(BUILD_DIR)/$(TARGET)_blob.c

disasm: $(BUILD_DIR)/$(TARGET).elf
	$(OBJDUMP) -d $<

clean:
	rm -rf $(BUILD_DIR)
