# FPGA Pin Assignment (iCE40 HX8K-CT256)

## Clock

| Signal | Pin | Description       |
|--------|-----|-------------------|
| CLK    | J3  | 12 MHz oscillator |

## Reset

| Signal | Pin | Description      |
|--------|-----|------------------|
| RST_N  | R9  | Active-low reset |

## PS/2 Keyboard Interface

| Signal   | Pin | Description         |
|----------|-----|---------------------|
| PS2_CLK  | T1  | Keyboard clock line |
| PS2_DATA | T2  | Keyboard data line  |

## LED Output

| Signal | Pin | Description                   |
|--------|-----|-------------------------------|
| LED[0] | B5  | Ciphertext output bit 0 (LSB) |
| LED[1] | B4  | Ciphertext output bit 1       |
| LED[2] | A2  | Ciphertext output bit 2       |
| LED[3] | A1  | Ciphertext output bit 3       |
| LED[4] | C5  | Ciphertext output bit 4       |
| LED[5] | C4  | Ciphertext output bit 5       |
| LED[6] | B3  | Ciphertext output bit 6       |
| LED[7] | C3  | Ciphertext output bit 7 (MSB) |

## Control

| Signal     | Pin | Description                                                |
|------------|-----|------------------------------------------------------------|
| LED_STROBE | D5  | Pulses high for one clock cycle when new LED byte is valid |

## Protocol

After the user types a message and presses Enter:

1. The FPGA encrypts the message
2. The ciphertext is output byte-by-byte on LED[7:0]
3. LED_STROBE pulses once per byte
4. Bytes are output MSB-first within each 64-bit block
