`timescale 1ns/1ps

module ps2_rx (
    input  wire       clk,
    input  wire       rst_n,
    input  wire       ps2_clk,
    input  wire       ps2_data,
    output reg  [7:0] rx_data,
    output reg        rx_valid
);

    reg [2:0] ps2_clk_sync;
    reg [1:0] ps2_data_sync;

    wire ps2_clk_fall;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            ps2_clk_sync  <= 3'b111;
            ps2_data_sync <= 2'b11;
        end else begin
            ps2_clk_sync  <= {ps2_clk_sync[1:0], ps2_clk};
            ps2_data_sync <= {ps2_data_sync[0], ps2_data};
        end
    end

    assign ps2_clk_fall = ps2_clk_sync[2] & ~ps2_clk_sync[1];

    reg [3:0] bit_cnt;
    reg [10:0] shift_reg;
    reg        receiving;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            bit_cnt   <= 4'd0;
            shift_reg <= 11'd0;
            receiving <= 1'b0;
            rx_data   <= 8'd0;
            rx_valid  <= 1'b0;
        end else begin
            rx_valid <= 1'b0;

            if (ps2_clk_fall) begin
                if (!receiving) begin
                    if (ps2_data_sync[1] == 1'b0) begin
                        receiving <= 1'b1;
                        shift_reg[0] <= ps2_data_sync[1];
                        bit_cnt <= 4'd1;
                    end
                end else begin
                    shift_reg[bit_cnt] <= ps2_data_sync[1];
                    bit_cnt <= bit_cnt + 4'd1;

                    if (bit_cnt == 4'd10) begin
                        receiving <= 1'b0;
                        bit_cnt   <= 4'd0;

                        if (shift_reg[0] == 1'b0 && ps2_data_sync[1] == 1'b1) begin
                            if (^shift_reg[9:1] == 1'b1) begin
                                rx_data  <= shift_reg[8:1];
                                rx_valid <= 1'b1;
                            end
                        end
                    end
                end
            end
        end
    end

endmodule
