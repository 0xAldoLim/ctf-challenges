`timescale 1ns/1ps

module led_output (
    input  wire       clk,
    input  wire       rst_n,
    input  wire [7:0] data_byte,
    input  wire       data_valid,
    input  wire       data_last,
    output reg  [7:0] led,
    output reg        led_strobe
);

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            led        <= 8'd0;
            led_strobe <= 1'b0;
        end else begin
            led_strobe <= 1'b0;
            if (data_valid) begin
                led        <= data_byte;
                led_strobe <= 1'b1;
            end
        end
    end

endmodule
