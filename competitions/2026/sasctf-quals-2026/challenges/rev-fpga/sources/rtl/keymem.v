`timescale 1ns/1ps

module keymem (
    input  wire        clk,
    input  wire [7:0]  addr,
    input  wire        rd,
    output reg  [31:0] data_out
);

    reg [31:0] mem [0:255];

    initial begin
        mem[0]  = 32'h4B455931; // K0 ("KEY1")
        mem[1]  = 32'h4B455932; // K1 ("KEY2")
        mem[2]  = 32'h4B455933; // K2 ("KEY3")
        mem[3]  = 32'h4B455934; // K3 ("KEY4")
        mem[4]  = 32'hDEADBEEF; // IV[0]
        mem[5]  = 32'hCAFEBABE; // IV[1]
        mem[6]  = 32'h243F6A88; // RC[0]
        mem[7]  = 32'h85A308D3; // RC[1]
        mem[8]  = 32'h13198A2E; // RC[2]
        mem[9]  = 32'h03707344; // RC[3]
        mem[10] = 32'hA4093822; // RC[4]
        mem[11] = 32'h299F31D0; // RC[5]
        mem[12] = 32'h082EFA98; // RC[6]
        mem[13] = 32'hEC4E6C89; // RC[7]
        mem[14] = 32'h452821E6; // RC[8]
        mem[15] = 32'h38D01377; // RC[9]
        mem[16] = 32'hBE5466CF; // RC[10]
        mem[17] = 32'h34E90C6C; // RC[11]
        mem[18] = 32'hC0AC29B7; // RC[12]
        mem[19] = 32'hC97C50DD; // RC[13]
        mem[20] = 32'h3F84D5B5; // RC[14]
        mem[21] = 32'hB5470917; // RC[15]
    end

    always @(posedge clk) begin
        if (rd)
            data_out <= mem[addr];
    end

endmodule
