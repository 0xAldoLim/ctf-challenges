VERILATOR ?= verilator
CXX ?= g++
RTL_DIR := ../rtl
TOP_MODULE := top
VFLAGS := -Wall -Wno-fatal -DVERILATOR --cc --exe --build
FLAG ?= "SAS{placeholder}"

RTL_SRCS := $(RTL_DIR)/ps2_rx.v \
            $(RTL_DIR)/scancode_fsm.v \
            $(RTL_DIR)/controller.v \
            $(RTL_DIR)/cipher.v \
            $(RTL_DIR)/sbox_rom.v \
            $(RTL_DIR)/keymem.v \
            $(RTL_DIR)/led_output.v \
            $(RTL_DIR)/decoy.v \
            $(RTL_DIR)/top.v

.PHONY: all clean run

all: obj_dir/Vtop

obj_dir/Vtop: $(RTL_SRCS) tb_top.cpp ps2_driver.h
	$(VERILATOR) $(VFLAGS) --top-module $(TOP_MODULE) \
		-CFLAGS "-I$(shell pwd)" \
		$(RTL_SRCS) tb_top.cpp -o Vtop

run: obj_dir/Vtop
	./obj_dir/Vtop $(FLAG)

clean:
	rm -rf obj_dir
