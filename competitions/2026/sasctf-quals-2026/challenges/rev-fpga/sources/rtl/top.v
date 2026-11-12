`timescale 1ns/1ps

module top (
    input  wire       CLK,
    input  wire       RST_N,
    input  wire       PS2_CLK,
    input  wire       PS2_DATA,
    output wire [7:0] LED,
    output wire       LED_STROBE,
    output wire       DECOY_OUT
);

    wire [7:0] rx_data;
    wire       rx_valid;

    ps2_rx u_ps2_rx (
        .clk      (CLK),
        .rst_n    (RST_N),
        .ps2_clk  (PS2_CLK),
        .ps2_data (PS2_DATA),
        .rx_data  (rx_data),
        .rx_valid (rx_valid)
    );

    wire [7:0] ascii_char;
    wire       ascii_valid;

    scancode_fsm u_scancode (
        .clk        (CLK),
        .rst_n      (RST_N),
        .scan_code  (rx_data),
        .scan_valid (rx_valid),
        .ascii_char (ascii_char),
        .ascii_valid(ascii_valid)
    );

    wire [7:0]  ctrl_keymem_addr;
    wire        ctrl_keymem_rd;
    wire [7:0]  ciph_keymem_addr;
    wire        ciph_keymem_rd;
    wire [7:0]  keymem_addr;
    wire        keymem_rd;
    wire [31:0] keymem_data;

    wire [7:0]  sbox_addr;
    wire        sbox_rd;
    wire [7:0]  sbox_data;

    wire [63:0] cipher_block_in;
    wire        cipher_start;
    wire [63:0] cipher_block_out;
    wire        cipher_done;

    wire cipher_active = ciph_keymem_rd;
    assign keymem_addr = cipher_active ? ciph_keymem_addr : ctrl_keymem_addr;
    assign keymem_rd   = cipher_active ? ciph_keymem_rd   : ctrl_keymem_rd;

    wire [7:0] out_byte;
    wire       out_valid;
    wire       out_last;

    controller u_ctrl (
        .clk            (CLK),
        .rst_n          (RST_N),
        .ascii_char     (ascii_char),
        .ascii_valid    (ascii_valid),
        .keymem_addr    (ctrl_keymem_addr),
        .keymem_rd      (ctrl_keymem_rd),
        .keymem_data    (keymem_data),
        .cipher_block_in(cipher_block_in),
        .cipher_start   (cipher_start),
        .cipher_block_out(cipher_block_out),
        .cipher_done    (cipher_done),
        .out_byte       (out_byte),
        .out_valid      (out_valid),
        .out_last       (out_last)
    );

    cipher u_cipher (
        .clk         (CLK),
        .rst_n       (RST_N),
        .block_in    (cipher_block_in),
        .start       (cipher_start),
        .keymem_data (keymem_data),
        .sbox_out    (sbox_data),
        .block_out   (cipher_block_out),
        .done        (cipher_done),
        .sbox_addr   (sbox_addr),
        .sbox_rd     (sbox_rd),
        .keymem_addr (ciph_keymem_addr),
        .keymem_rd   (ciph_keymem_rd)
    );

    sbox_rom u_sbox (
        .clk      (CLK),
        .addr     (sbox_addr),
        .rd       (sbox_rd),
        .data_out (sbox_data)
    );

    keymem u_keymem (
        .clk      (CLK),
        .addr     (keymem_addr),
        .rd       (keymem_rd),
        .data_out (keymem_data)
    );

    led_output u_led (
        .clk        (CLK),
        .rst_n      (RST_N),
        .data_byte  (out_byte),
        .data_valid (out_valid),
        .data_last  (out_last),
        .led        (LED),
        .led_strobe (LED_STROBE)
    );

    decoy u_decoy (
        .clk       (CLK),
        .rst_n     (RST_N),
        .ps2_data  (PS2_DATA),
        .decoy_out (DECOY_OUT)
    );

endmodule
