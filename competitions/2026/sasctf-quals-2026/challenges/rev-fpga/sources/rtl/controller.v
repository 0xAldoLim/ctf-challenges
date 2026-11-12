`timescale 1ns/1ps

module controller (
    input  wire        clk,
    input  wire        rst_n,
    input  wire [7:0]  ascii_char,
    input  wire        ascii_valid,
    // Keymem interface
    output reg  [7:0]  keymem_addr,
    output reg         keymem_rd,
    input  wire [31:0] keymem_data,
    // Cipher interface
    output reg  [63:0] cipher_block_in,
    output reg         cipher_start,
    input  wire [63:0] cipher_block_out,
    input  wire        cipher_done,
    // LED output interface
    output reg  [7:0]  out_byte,
    output reg         out_valid,
    output reg         out_last
);

    localparam ST_IDLE       = 3'd0;
    localparam ST_COLLECTING = 3'd1;
    localparam ST_PADDING    = 3'd2;
    localparam ST_ENCRYPTING = 3'd3;
    localparam ST_OUTPUTTING = 3'd4;
    localparam ST_DONE       = 3'd5;

    localparam PAD_IV0      = 3'd0;
    localparam PAD_IV0_WAIT = 3'd1;
    localparam PAD_IV1      = 3'd2;
    localparam PAD_IV1_WAIT = 3'd3;
    localparam PAD_IV2      = 3'd4;
    localparam PAD_DONE     = 3'd5;

    localparam ENC_PREP  = 2'd0;
    localparam ENC_START = 2'd1;
    localparam ENC_WAIT  = 2'd2;
    localparam ENC_STORE = 2'd3;

    reg [2:0]  state;
    reg [2:0]  sub_state;

    reg [7:0]  plaintext_buf [0:63];
    reg [7:0]  ciphertext_buf [0:63];
    reg [6:0]  byte_cnt;
    reg [3:0]  block_cnt;
    reg [3:0]  cur_block;
    reg [6:0]  out_idx;
    reg [6:0]  total_ct_bytes;

    reg [63:0] prev_ct;

    integer i;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state        <= ST_IDLE;
            sub_state    <= 3'd0;
            byte_cnt     <= 7'd0;
            block_cnt    <= 4'd0;
            cur_block    <= 4'd0;
            out_idx      <= 7'd0;
            total_ct_bytes <= 7'd0;
            prev_ct      <= 64'd0;
            cipher_start <= 1'b0;
            cipher_block_in <= 64'd0;
            keymem_addr  <= 8'd0;
            keymem_rd    <= 1'b0;
            out_byte     <= 8'd0;
            out_valid    <= 1'b0;
            out_last     <= 1'b0;
            for (i = 0; i < 64; i = i + 1) begin
                plaintext_buf[i] <= 8'd0;
                ciphertext_buf[i] <= 8'd0;
            end
        end else begin
            cipher_start <= 1'b0;
            keymem_rd    <= 1'b0;
            out_valid    <= 1'b0;
            out_last     <= 1'b0;

            case (state)
                ST_IDLE: begin
                    if (ascii_valid) begin
                        if (ascii_char == 8'h0D) begin
                            if (byte_cnt > 0) begin
                                state     <= ST_PADDING;
                                sub_state <= PAD_IV0;
                            end
                        end else begin
                            plaintext_buf[byte_cnt] <= ascii_char;
                            byte_cnt <= byte_cnt + 7'd1;
                            state    <= ST_COLLECTING;
                        end
                    end
                end

                ST_COLLECTING: begin
                    if (ascii_valid) begin
                        if (ascii_char == 8'h0D) begin
                            state     <= ST_PADDING;
                            sub_state <= PAD_IV0;
                        end else if (byte_cnt < 7'd64) begin
                            plaintext_buf[byte_cnt] <= ascii_char;
                            byte_cnt <= byte_cnt + 7'd1;
                        end
                    end
                end

                ST_PADDING: begin
                    case (sub_state)
                        PAD_IV0: begin
                            keymem_addr <= 8'd4;
                            keymem_rd   <= 1'b1;
                            sub_state   <= PAD_IV0_WAIT;
                        end
                        PAD_IV0_WAIT: begin
                            keymem_rd <= 1'b1;
                            sub_state <= PAD_IV1;
                        end
                        PAD_IV1: begin
                            prev_ct[63:32] <= keymem_data;
                            keymem_addr    <= 8'd5;
                            keymem_rd      <= 1'b1;
                            sub_state      <= PAD_IV1_WAIT;
                        end
                        PAD_IV1_WAIT: begin
                            keymem_rd <= 1'b1;
                            sub_state <= PAD_IV2;
                        end
                        PAD_IV2: begin
                            prev_ct[31:0] <= keymem_data;
                            sub_state     <= PAD_DONE;
                        end
                        PAD_DONE: begin
                            if (byte_cnt[2:0] != 3'd0) begin
                                block_cnt <= byte_cnt[6:3] + 4'd1;
                                total_ct_bytes <= {byte_cnt[6:3] + 4'd1, 3'd0};
                            end else begin
                                block_cnt <= byte_cnt[6:3];
                                total_ct_bytes <= byte_cnt;
                            end
                            cur_block  <= 4'd0;
                            sub_state  <= ENC_PREP;
                            state      <= ST_ENCRYPTING;
                        end
                    endcase
                end

                ST_ENCRYPTING: begin
                    case (sub_state)
                        ENC_PREP: begin
                            begin : prep_block
                                reg [6:0] base;
                                base = {cur_block, 3'd0};
                                cipher_block_in <= {
                                    plaintext_buf[base + 0] ^ prev_ct[63:56],
                                    plaintext_buf[base + 1] ^ prev_ct[55:48],
                                    plaintext_buf[base + 2] ^ prev_ct[47:40],
                                    plaintext_buf[base + 3] ^ prev_ct[39:32],
                                    plaintext_buf[base + 4] ^ prev_ct[31:24],
                                    plaintext_buf[base + 5] ^ prev_ct[23:16],
                                    plaintext_buf[base + 6] ^ prev_ct[15:8],
                                    plaintext_buf[base + 7] ^ prev_ct[7:0]
                                };
                            end
                            sub_state <= ENC_START;
                        end
                        ENC_START: begin
                            cipher_start <= 1'b1;
                            sub_state    <= ENC_WAIT;
                        end
                        ENC_WAIT: begin
                            if (cipher_done) begin
                                sub_state <= ENC_STORE;
                            end
                        end
                        ENC_STORE: begin
                            begin : store_block
                                reg [6:0] base;
                                base = {cur_block, 3'd0};
                                ciphertext_buf[base + 0] <= cipher_block_out[63:56];
                                ciphertext_buf[base + 1] <= cipher_block_out[55:48];
                                ciphertext_buf[base + 2] <= cipher_block_out[47:40];
                                ciphertext_buf[base + 3] <= cipher_block_out[39:32];
                                ciphertext_buf[base + 4] <= cipher_block_out[31:24];
                                ciphertext_buf[base + 5] <= cipher_block_out[23:16];
                                ciphertext_buf[base + 6] <= cipher_block_out[15:8];
                                ciphertext_buf[base + 7] <= cipher_block_out[7:0];
                            end
                            prev_ct <= cipher_block_out;

                            if (cur_block + 4'd1 == block_cnt) begin
                                state     <= ST_OUTPUTTING;
                                out_idx   <= 7'd0;
                            end else begin
                                cur_block <= cur_block + 4'd1;
                                sub_state <= ENC_PREP;
                            end
                        end
                    endcase
                end

                ST_OUTPUTTING: begin
                    out_byte  <= ciphertext_buf[out_idx];
                    out_valid <= 1'b1;
                    if (out_idx + 7'd1 == total_ct_bytes) begin
                        out_last <= 1'b1;
                        state    <= ST_DONE;
                    end else begin
                        out_idx <= out_idx + 7'd1;
                    end
                end

                ST_DONE: begin
                end
            endcase
        end
    end

endmodule
