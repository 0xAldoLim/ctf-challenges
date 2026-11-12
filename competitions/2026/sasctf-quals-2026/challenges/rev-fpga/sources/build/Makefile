.PHONY: all clean

all: firmware.bin

hardware.json: ../rtl/*.v synth.ys
	yosys -s synth.ys

hardware.asc: hardware.json ../constraints/ice40hx8k.pcf
	nextpnr-ice40 --hx8k --package ct256 --pcf ../constraints/ice40hx8k.pcf --json hardware.json --asc hardware.asc

firmware.bin: hardware.asc
	icepack hardware.asc firmware.bin

clean:
	rm -f hardware.json hardware.asc firmware.bin
