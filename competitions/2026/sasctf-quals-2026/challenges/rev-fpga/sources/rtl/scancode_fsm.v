`timescale 1ns/1ps

module scancode_fsm (
    input  wire       clk,
    input  wire       rst_n,
    input  wire [7:0] scan_code,
    input  wire       scan_valid,
    output reg  [7:0] ascii_char,
    output reg        ascii_valid
);

    localparam ST_IDLE     = 2'd0;
    localparam ST_BREAK    = 2'd1;
    localparam ST_EXTENDED = 2'd2;
    localparam ST_EXT_BRK  = 2'd3;

    reg [1:0] state;
    reg       shift_held;

    reg [7:0] ascii_lut;
    reg [7:0] ascii_shift_lut;

    always @(*) begin
        case (scan_code)
            8'h1C: ascii_lut = 8'h61;
            8'h32: ascii_lut = 8'h62;
            8'h21: ascii_lut = 8'h63;
            8'h23: ascii_lut = 8'h64;
            8'h24: ascii_lut = 8'h65;
            8'h2B: ascii_lut = 8'h66;
            8'h34: ascii_lut = 8'h67;
            8'h33: ascii_lut = 8'h68;
            8'h43: ascii_lut = 8'h69;
            8'h3B: ascii_lut = 8'h6A;
            8'h42: ascii_lut = 8'h6B;
            8'h4B: ascii_lut = 8'h6C;
            8'h3A: ascii_lut = 8'h6D;
            8'h31: ascii_lut = 8'h6E;
            8'h44: ascii_lut = 8'h6F;
            8'h4D: ascii_lut = 8'h70;
            8'h15: ascii_lut = 8'h71;
            8'h2D: ascii_lut = 8'h72;
            8'h1B: ascii_lut = 8'h73;
            8'h2C: ascii_lut = 8'h74;
            8'h3C: ascii_lut = 8'h75;
            8'h2A: ascii_lut = 8'h76;
            8'h1D: ascii_lut = 8'h77;
            8'h22: ascii_lut = 8'h78;
            8'h35: ascii_lut = 8'h79;
            8'h1A: ascii_lut = 8'h7A;
            8'h45: ascii_lut = 8'h30;
            8'h16: ascii_lut = 8'h31;
            8'h1E: ascii_lut = 8'h32;
            8'h26: ascii_lut = 8'h33;
            8'h25: ascii_lut = 8'h34;
            8'h2E: ascii_lut = 8'h35;
            8'h36: ascii_lut = 8'h36;
            8'h3D: ascii_lut = 8'h37;
            8'h3E: ascii_lut = 8'h38;
            8'h46: ascii_lut = 8'h39;
            8'h29: ascii_lut = 8'h20;
            8'h5A: ascii_lut = 8'h0D;
            8'h4E: ascii_lut = 8'h2D;
            8'h55: ascii_lut = 8'h3D;
            8'h54: ascii_lut = 8'h5B;
            8'h5B: ascii_lut = 8'h5D;
            8'h4C: ascii_lut = 8'h3B;
            8'h52: ascii_lut = 8'h27;
            8'h41: ascii_lut = 8'h2C;
            8'h49: ascii_lut = 8'h2E;
            8'h4A: ascii_lut = 8'h2F;
            8'h5D: ascii_lut = 8'h5C;
            8'h0E: ascii_lut = 8'h60;
            default: ascii_lut = 8'h00;
        endcase
    end

    always @(*) begin
        case (scan_code)
            8'h1C: ascii_shift_lut = 8'h41;
            8'h32: ascii_shift_lut = 8'h42;
            8'h21: ascii_shift_lut = 8'h43;
            8'h23: ascii_shift_lut = 8'h44;
            8'h24: ascii_shift_lut = 8'h45;
            8'h2B: ascii_shift_lut = 8'h46;
            8'h34: ascii_shift_lut = 8'h47;
            8'h33: ascii_shift_lut = 8'h48;
            8'h43: ascii_shift_lut = 8'h49;
            8'h3B: ascii_shift_lut = 8'h4A;
            8'h42: ascii_shift_lut = 8'h4B;
            8'h4B: ascii_shift_lut = 8'h4C;
            8'h3A: ascii_shift_lut = 8'h4D;
            8'h31: ascii_shift_lut = 8'h4E;
            8'h44: ascii_shift_lut = 8'h4F;
            8'h4D: ascii_shift_lut = 8'h50;
            8'h15: ascii_shift_lut = 8'h51;
            8'h2D: ascii_shift_lut = 8'h52;
            8'h1B: ascii_shift_lut = 8'h53;
            8'h2C: ascii_shift_lut = 8'h54;
            8'h3C: ascii_shift_lut = 8'h55;
            8'h2A: ascii_shift_lut = 8'h56;
            8'h1D: ascii_shift_lut = 8'h57;
            8'h22: ascii_shift_lut = 8'h58;
            8'h35: ascii_shift_lut = 8'h59;
            8'h1A: ascii_shift_lut = 8'h5A;
            8'h45: ascii_shift_lut = 8'h29;
            8'h16: ascii_shift_lut = 8'h21;
            8'h1E: ascii_shift_lut = 8'h40;
            8'h26: ascii_shift_lut = 8'h23;
            8'h25: ascii_shift_lut = 8'h24;
            8'h2E: ascii_shift_lut = 8'h25;
            8'h36: ascii_shift_lut = 8'h5E;
            8'h3D: ascii_shift_lut = 8'h26;
            8'h3E: ascii_shift_lut = 8'h2A;
            8'h46: ascii_shift_lut = 8'h28;
            8'h29: ascii_shift_lut = 8'h20;
            8'h5A: ascii_shift_lut = 8'h0D;
            8'h4E: ascii_shift_lut = 8'h5F;
            8'h55: ascii_shift_lut = 8'h2B;
            8'h54: ascii_shift_lut = 8'h7B;
            8'h5B: ascii_shift_lut = 8'h7D;
            8'h4C: ascii_shift_lut = 8'h3A;
            8'h52: ascii_shift_lut = 8'h22;
            8'h41: ascii_shift_lut = 8'h3C;
            8'h49: ascii_shift_lut = 8'h3E;
            8'h4A: ascii_shift_lut = 8'h3F;
            8'h5D: ascii_shift_lut = 8'h7C;
            8'h0E: ascii_shift_lut = 8'h7E;
            default: ascii_shift_lut = 8'h00;
        endcase
    end

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state       <= ST_IDLE;
            ascii_char  <= 8'd0;
            ascii_valid <= 1'b0;
            shift_held  <= 1'b0;
        end else begin
            ascii_valid <= 1'b0;

            if (scan_valid) begin
                case (state)
                    ST_IDLE: begin
                        if (scan_code == 8'hF0) begin
                            state <= ST_BREAK;
                        end else if (scan_code == 8'hE0) begin
                            state <= ST_EXTENDED;
                        end else if (scan_code == 8'h12 || scan_code == 8'h59) begin
                            shift_held <= 1'b1;
                        end else begin
                            if (shift_held) begin
                                if (ascii_shift_lut != 8'h00) begin
                                    ascii_char  <= ascii_shift_lut;
                                    ascii_valid <= 1'b1;
                                end
                            end else begin
                                if (ascii_lut != 8'h00) begin
                                    ascii_char  <= ascii_lut;
                                    ascii_valid <= 1'b1;
                                end
                            end
                        end
                    end
                    ST_BREAK: begin
                        if (scan_code == 8'h12 || scan_code == 8'h59) begin
                            shift_held <= 1'b0;
                        end
                        state <= ST_IDLE;
                    end
                    ST_EXTENDED: begin
                        if (scan_code == 8'hF0) begin
                            state <= ST_EXT_BRK;
                        end else begin
                            state <= ST_IDLE;
                        end
                    end
                    ST_EXT_BRK: begin
                        state <= ST_IDLE;
                    end
                endcase
            end
        end
    end

endmodule
