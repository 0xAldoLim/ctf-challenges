# Build the U-mode trusted-lib wrapper blob (baked into QEMU at 0x80000000).
CROSS_COMPILE ?= riscv64-linux-gnu-
CC      := $(CROSS_COMPILE)gcc
OBJCOPY := $(CROSS_COMPILE)objcopy
OBJDUMP := $(CROSS_COMPILE)objdump

BUILD_DIR := build
TARGET    := trusted_lib
BASE_ADDR := 0x80000000

ARCH_FLAGS := -march=rv64im -mabi=lp64 -fno-omit-frame-pointer -fno-optimize-sibling-calls \
              -static -nostdlib -nostartfiles
CFLAGS     := $(ARCH_FLAGS) -O2 -ffreestanding -Wall -Wextra -I.
LDFLAGS    := $(ARCH_FLAGS) -T ld_script.ld -Wl,--build-id=none -Wl,-Map="$(BUILD_DIR)/$(TARGET).map"

OBJS := $(BUILD_DIR)/trusted_lib.o

.PHONY: all blob disasm clean
all: $(BUILD_DIR)/$(TARGET).bin
$(BUILD_DIR):
	mkdir -p $@
$(BUILD_DIR)/%.o: %.c | $(BUILD_DIR)
	$(CC) $(CFLAGS) -c $< -o $@
$(BUILD_DIR)/$(TARGET).elf: $(OBJS) trusted_scrub_rv64.S ld_script.ld
	$(CC) $(LDFLAGS) $(OBJS) trusted_scrub_rv64.S -o $@
$(BUILD_DIR)/$(TARGET).bin: $(BUILD_DIR)/$(TARGET).elf
	$(OBJCOPY) --change-addresses=-$(BASE_ADDR) -O binary $< $@
blob: $(BUILD_DIR)/$(TARGET).bin
	xxd -i $(BUILD_DIR)/$(TARGET).bin > $(BUILD_DIR)/$(TARGET)_blob.c
disasm: $(BUILD_DIR)/$(TARGET).elf
	$(OBJDUMP) -d $<
clean:
	rm -rf $(BUILD_DIR)
