## Title
Lut, I am your father

## Description
We intercepted a mysterious FPGA bitstream and its encrypted output. The device was connected to a PS/2 keyboard - someone typed a secret message, the FPGA encrypted it, and the ciphertext was captured from the LED outputs.

The bitstream targets a Lattice iCE40 HX8K FPGA (CT256 package). You are given:
- firmware.bin - the iCE40 bitstream
- ciphertext.hex - the captured ciphertext (hex-encoded, one 64-bit block per line)
- pinout.md - pin assignment documentation
