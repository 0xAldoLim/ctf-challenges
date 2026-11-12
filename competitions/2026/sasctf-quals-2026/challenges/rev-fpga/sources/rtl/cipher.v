`timescale 1ns/1ps

module cipher (
    input  wire        clk,
    input  wire        rst_n,
    input  wire [63:0] block_in,
    input  wire        start,
    input  wire [31:0] keymem_data,
    input  wire [7:0]  sbox_out,
    output reg  [63:0] block_out,
    output reg         done,
    output reg  [7:0]  sbox_addr,
    output reg         sbox_rd,
    output reg  [7:0]  keymem_addr,
    output reg         keymem_rd
);

    localparam ST_IDLE    = 4'd0;
    localparam ST_LOAD_K  = 4'd1;
    localparam ST_LOAD_RC = 4'd2;
    localparam ST_PREP    = 4'd3;
    localparam ST_SBOX0   = 4'd4;
    localparam ST_SBOX1   = 4'd5;
    localparam ST_SBOX2   = 4'd6;
    localparam ST_SBOX3   = 4'd7;
    localparam ST_SBOX4   = 4'd10;
    localparam ST_MIX     = 4'd8;
    localparam ST_DONE    = 4'd9;

    reg [3:0]  state;
    reg [4:0]  cnt;
    reg [3:0]  round_cnt;
    reg        keys_loaded;

    reg [31:0] K [0:3];
    reg [31:0] RC [0:15];
    reg [31:0] L, R;
    reg [31:0] round_key;
    reg [7:0]  s0, s1, s2;

    function [31:0] rotl32;
        input [31:0] val;
        input [4:0]  amt;
        begin
            rotl32 = (val << amt) | (val >> (5'd0 - amt));
        end
    endfunction

    function [4:0] key_rot_amt;
        input [3:0] rnd;
        begin
            case (rnd)
                4'd0:  key_rot_amt = 5'd0;
                4'd1:  key_rot_amt = 5'd3;
                4'd2:  key_rot_amt = 5'd6;
                4'd3:  key_rot_amt = 5'd9;
                4'd4:  key_rot_amt = 5'd12;
                4'd5:  key_rot_amt = 5'd15;
                4'd6:  key_rot_amt = 5'd18;
                4'd7:  key_rot_amt = 5'd21;
                4'd8:  key_rot_amt = 5'd24;
                4'd9:  key_rot_amt = 5'd27;
                4'd10: key_rot_amt = 5'd30;
                4'd11: key_rot_amt = 5'd1;
                4'd12: key_rot_amt = 5'd4;
                4'd13: key_rot_amt = 5'd7;
                4'd14: key_rot_amt = 5'd10;
                4'd15: key_rot_amt = 5'd13;
            endcase
        end
    endfunction

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state       <= ST_IDLE;
            cnt         <= 5'd0;
            round_cnt   <= 4'd0;
            keys_loaded <= 1'b0;
            done        <= 1'b0;
            block_out   <= 64'd0;
            sbox_addr   <= 8'd0;
            sbox_rd     <= 1'b0;
            keymem_addr <= 8'd0;
            keymem_rd   <= 1'b0;
            L           <= 32'd0;
            R           <= 32'd0;
            round_key   <= 32'd0;
            s0 <= 8'd0; s1 <= 8'd0; s2 <= 8'd0;
        end else begin
            done      <= 1'b0;
            sbox_rd   <= 1'b0;
            keymem_rd <= 1'b0;

            case (state)
                ST_IDLE: begin
                    if (start) begin
                        if (!keys_loaded) begin
                            keymem_addr <= 8'd0;
                            keymem_rd   <= 1'b1;
                            cnt         <= 5'd0;
                            state       <= ST_LOAD_K;
                        end else begin
                            L         <= block_in[63:32];
                            R         <= block_in[31:0];
                            round_cnt <= 4'd0;
                            state     <= ST_PREP;
                        end
                    end
                end

                ST_LOAD_K: begin
                    if (cnt == 5'd0) begin
                        keymem_addr <= 8'd1;
                        cnt         <= 5'd1;
                    end else begin
                        K[cnt - 5'd1] <= keymem_data;
                        if (cnt == 5'd4) begin
                            keymem_addr <= 8'd6;
                            cnt         <= 5'd0;
                            state       <= ST_LOAD_RC;
                        end else begin
                            keymem_addr <= cnt + 8'd1;
                            cnt         <= cnt + 5'd1;
                        end
                    end
                    keymem_rd <= 1'b1;
                end

                ST_LOAD_RC: begin
                    if (cnt[0] == 1'b0) begin
                        cnt <= cnt + 5'd1;
                    end else begin
                        RC[cnt[4:1]] <= keymem_data;
                        if (cnt[4:1] == 4'd15) begin
                            keys_loaded <= 1'b1;
                            L           <= block_in[63:32];
                            R           <= block_in[31:0];
                            round_cnt   <= 4'd0;
                            state       <= ST_PREP;
                        end else begin
                            keymem_addr <= {2'b0, cnt[4:1]} + 8'd7;
                            cnt         <= cnt + 5'd1;
                        end
                    end
                    keymem_rd <= 1'b1;
                end

                ST_PREP: begin
                    case (round_cnt[1:0])
                        2'd0: round_key <= rotl32(K[0], key_rot_amt(round_cnt)) ^ RC[round_cnt];
                        2'd1: round_key <= rotl32(K[1], key_rot_amt(round_cnt)) ^ RC[round_cnt];
                        2'd2: round_key <= rotl32(K[2], key_rot_amt(round_cnt)) ^ RC[round_cnt];
                        2'd3: round_key <= rotl32(K[3], key_rot_amt(round_cnt)) ^ RC[round_cnt];
                    endcase
                    state <= ST_SBOX0;
                end

                ST_SBOX0: begin
                    sbox_addr <= R[7:0] ^ round_key[7:0];
                    sbox_rd   <= 1'b1;
                    state     <= ST_SBOX1;
                end

                ST_SBOX1: begin
                    sbox_addr <= R[15:8] ^ round_key[15:8];
                    sbox_rd   <= 1'b1;
                    state     <= ST_SBOX2;
                end

                ST_SBOX2: begin
                    s0        <= sbox_out;
                    sbox_addr <= R[23:16] ^ round_key[23:16];
                    sbox_rd   <= 1'b1;
                    state     <= ST_SBOX3;
                end

                ST_SBOX3: begin
                    s1        <= sbox_out;
                    sbox_addr <= R[31:24] ^ round_key[31:24];
                    sbox_rd   <= 1'b1;
                    state     <= ST_SBOX4;
                end

                ST_SBOX4: begin
                    s2        <= sbox_out;
                    sbox_rd   <= 1'b1;
                    state     <= ST_MIX;
                end

                ST_MIX: begin
                    begin : mix_compute
                        reg [7:0] r0, r1, r2, r3;
                        reg [7:0] d0, d1, d2, d3;
                        reg [31:0] diffused, rotated, f_out;

                        r0 = s0;
                        r1 = s1;
                        r2 = s2;
                        r3 = sbox_out;

                        d0 = r0 ^ r3;
                        d1 = r1 ^ r0;
                        d2 = r2 ^ r1;
                        d3 = r3 ^ r2;

                        diffused = {d3, d2, d1, d0};

                        case (round_key[1:0])
                            2'd0: rotated = diffused;
                            2'd1: rotated = {diffused[23:0], diffused[31:24]};
                            2'd2: rotated = {diffused[15:0], diffused[31:16]};
                            2'd3: rotated = {diffused[7:0],  diffused[31:8]};
                        endcase

                        f_out = rotated;

                        L <= R;
                        R <= L ^ f_out;
                    end

                    if (round_cnt == 4'd15) begin
                        state <= ST_DONE;
                    end else begin
                        round_cnt <= round_cnt + 4'd1;
                        state     <= ST_PREP;
                    end
                end

                ST_DONE: begin
                    block_out <= {L, R};
                    done      <= 1'b1;
                    state     <= ST_IDLE;
                end
            endcase
        end
    end

endmodule
