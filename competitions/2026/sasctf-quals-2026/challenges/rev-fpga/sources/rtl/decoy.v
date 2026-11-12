`timescale 1ns/1ps

module decoy (
    input  wire       clk,
    input  wire       rst_n,
    input  wire       ps2_data,
    output wire       decoy_out
);
    (* keep *)
    reg [31:0] lfsr;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            lfsr <= 32'hACE1CAFE;
        end else begin
            lfsr <= {lfsr[30:0], lfsr[31] ^ lfsr[21] ^ lfsr[1] ^ lfsr[0]};
        end
    end

    (* keep *)
    reg [7:0] fake_sbox [0:255];
    initial begin
        fake_sbox[8'h00]=8'h52; fake_sbox[8'h01]=8'h09; fake_sbox[8'h02]=8'h6a; fake_sbox[8'h03]=8'hd5;
        fake_sbox[8'h04]=8'h30; fake_sbox[8'h05]=8'h36; fake_sbox[8'h06]=8'ha5; fake_sbox[8'h07]=8'h38;
        fake_sbox[8'h08]=8'hbf; fake_sbox[8'h09]=8'h40; fake_sbox[8'h0a]=8'ha3; fake_sbox[8'h0b]=8'h9e;
        fake_sbox[8'h0c]=8'h81; fake_sbox[8'h0d]=8'hf3; fake_sbox[8'h0e]=8'hd7; fake_sbox[8'h0f]=8'hfb;
        fake_sbox[8'h10]=8'h7c; fake_sbox[8'h11]=8'he3; fake_sbox[8'h12]=8'h39; fake_sbox[8'h13]=8'h82;
        fake_sbox[8'h14]=8'h9b; fake_sbox[8'h15]=8'h2f; fake_sbox[8'h16]=8'hff; fake_sbox[8'h17]=8'h87;
        fake_sbox[8'h18]=8'h34; fake_sbox[8'h19]=8'h8e; fake_sbox[8'h1a]=8'h43; fake_sbox[8'h1b]=8'h44;
        fake_sbox[8'h1c]=8'hc4; fake_sbox[8'h1d]=8'hde; fake_sbox[8'h1e]=8'he9; fake_sbox[8'h1f]=8'hcb;
        fake_sbox[8'h20]=8'h54; fake_sbox[8'h21]=8'h7b; fake_sbox[8'h22]=8'h94; fake_sbox[8'h23]=8'h32;
        fake_sbox[8'h24]=8'ha6; fake_sbox[8'h25]=8'hc2; fake_sbox[8'h26]=8'h23; fake_sbox[8'h27]=8'h3d;
        fake_sbox[8'h28]=8'hee; fake_sbox[8'h29]=8'h4c; fake_sbox[8'h2a]=8'h95; fake_sbox[8'h2b]=8'h0b;
        fake_sbox[8'h2c]=8'h42; fake_sbox[8'h2d]=8'hfa; fake_sbox[8'h2e]=8'hc3; fake_sbox[8'h2f]=8'h4e;
        fake_sbox[8'h30]=8'h08; fake_sbox[8'h31]=8'h2e; fake_sbox[8'h32]=8'ha1; fake_sbox[8'h33]=8'h66;
        fake_sbox[8'h34]=8'h28; fake_sbox[8'h35]=8'hd9; fake_sbox[8'h36]=8'h24; fake_sbox[8'h37]=8'hb2;
        fake_sbox[8'h38]=8'h76; fake_sbox[8'h39]=8'h5b; fake_sbox[8'h3a]=8'ha2; fake_sbox[8'h3b]=8'h49;
        fake_sbox[8'h3c]=8'h6d; fake_sbox[8'h3d]=8'h8b; fake_sbox[8'h3e]=8'hd1; fake_sbox[8'h3f]=8'h25;
        fake_sbox[8'h40]=8'h72; fake_sbox[8'h41]=8'hf8; fake_sbox[8'h42]=8'hf6; fake_sbox[8'h43]=8'h64;
        fake_sbox[8'h44]=8'h86; fake_sbox[8'h45]=8'h68; fake_sbox[8'h46]=8'h98; fake_sbox[8'h47]=8'h16;
        fake_sbox[8'h48]=8'hd4; fake_sbox[8'h49]=8'ha4; fake_sbox[8'h4a]=8'h5c; fake_sbox[8'h4b]=8'hcc;
        fake_sbox[8'h4c]=8'h5d; fake_sbox[8'h4d]=8'h65; fake_sbox[8'h4e]=8'hb6; fake_sbox[8'h4f]=8'h92;
        fake_sbox[8'h50]=8'h6c; fake_sbox[8'h51]=8'h70; fake_sbox[8'h52]=8'h48; fake_sbox[8'h53]=8'h50;
        fake_sbox[8'h54]=8'hfd; fake_sbox[8'h55]=8'hed; fake_sbox[8'h56]=8'hb9; fake_sbox[8'h57]=8'hda;
        fake_sbox[8'h58]=8'h5e; fake_sbox[8'h59]=8'h15; fake_sbox[8'h5a]=8'h46; fake_sbox[8'h5b]=8'h57;
        fake_sbox[8'h5c]=8'ha7; fake_sbox[8'h5d]=8'h8d; fake_sbox[8'h5e]=8'h9d; fake_sbox[8'h5f]=8'h84;
        fake_sbox[8'h60]=8'h90; fake_sbox[8'h61]=8'hd8; fake_sbox[8'h62]=8'hab; fake_sbox[8'h63]=8'h00;
        fake_sbox[8'h64]=8'h8c; fake_sbox[8'h65]=8'hbc; fake_sbox[8'h66]=8'hd3; fake_sbox[8'h67]=8'h0a;
        fake_sbox[8'h68]=8'hf7; fake_sbox[8'h69]=8'he4; fake_sbox[8'h6a]=8'h58; fake_sbox[8'h6b]=8'h05;
        fake_sbox[8'h6c]=8'hb8; fake_sbox[8'h6d]=8'hb3; fake_sbox[8'h6e]=8'h45; fake_sbox[8'h6f]=8'h06;
        fake_sbox[8'h70]=8'hd0; fake_sbox[8'h71]=8'h2c; fake_sbox[8'h72]=8'h1e; fake_sbox[8'h73]=8'h8f;
        fake_sbox[8'h74]=8'hca; fake_sbox[8'h75]=8'h3f; fake_sbox[8'h76]=8'h0f; fake_sbox[8'h77]=8'h02;
        fake_sbox[8'h78]=8'hc1; fake_sbox[8'h79]=8'haf; fake_sbox[8'h7a]=8'hbd; fake_sbox[8'h7b]=8'h03;
        fake_sbox[8'h7c]=8'h01; fake_sbox[8'h7d]=8'h13; fake_sbox[8'h7e]=8'h8a; fake_sbox[8'h7f]=8'h6b;
        fake_sbox[8'h80]=8'h3a; fake_sbox[8'h81]=8'h91; fake_sbox[8'h82]=8'h11; fake_sbox[8'h83]=8'h41;
        fake_sbox[8'h84]=8'h4f; fake_sbox[8'h85]=8'h67; fake_sbox[8'h86]=8'hdc; fake_sbox[8'h87]=8'hea;
        fake_sbox[8'h88]=8'h97; fake_sbox[8'h89]=8'hf2; fake_sbox[8'h8a]=8'hcf; fake_sbox[8'h8b]=8'hce;
        fake_sbox[8'h8c]=8'hf0; fake_sbox[8'h8d]=8'hb4; fake_sbox[8'h8e]=8'he6; fake_sbox[8'h8f]=8'h73;
        fake_sbox[8'h90]=8'h96; fake_sbox[8'h91]=8'hac; fake_sbox[8'h92]=8'h74; fake_sbox[8'h93]=8'h22;
        fake_sbox[8'h94]=8'he7; fake_sbox[8'h95]=8'had; fake_sbox[8'h96]=8'h35; fake_sbox[8'h97]=8'h85;
        fake_sbox[8'h98]=8'he2; fake_sbox[8'h99]=8'hf9; fake_sbox[8'h9a]=8'h37; fake_sbox[8'h9b]=8'he8;
        fake_sbox[8'h9c]=8'h1c; fake_sbox[8'h9d]=8'h75; fake_sbox[8'h9e]=8'hdf; fake_sbox[8'h9f]=8'h6e;
        fake_sbox[8'ha0]=8'h47; fake_sbox[8'ha1]=8'hf1; fake_sbox[8'ha2]=8'h1a; fake_sbox[8'ha3]=8'h71;
        fake_sbox[8'ha4]=8'h1d; fake_sbox[8'ha5]=8'h29; fake_sbox[8'ha6]=8'hc5; fake_sbox[8'ha7]=8'h89;
        fake_sbox[8'ha8]=8'h6f; fake_sbox[8'ha9]=8'hb7; fake_sbox[8'haa]=8'h62; fake_sbox[8'hab]=8'h0e;
        fake_sbox[8'hac]=8'haa; fake_sbox[8'had]=8'h18; fake_sbox[8'hae]=8'hbe; fake_sbox[8'haf]=8'h1b;
        fake_sbox[8'hb0]=8'hfc; fake_sbox[8'hb1]=8'h56; fake_sbox[8'hb2]=8'h3e; fake_sbox[8'hb3]=8'h4b;
        fake_sbox[8'hb4]=8'hc6; fake_sbox[8'hb5]=8'hd2; fake_sbox[8'hb6]=8'h79; fake_sbox[8'hb7]=8'h20;
        fake_sbox[8'hb8]=8'h9a; fake_sbox[8'hb9]=8'hdb; fake_sbox[8'hba]=8'hc0; fake_sbox[8'hbb]=8'hfe;
        fake_sbox[8'hbc]=8'h78; fake_sbox[8'hbd]=8'hcd; fake_sbox[8'hbe]=8'h5a; fake_sbox[8'hbf]=8'hf4;
        fake_sbox[8'hc0]=8'h1f; fake_sbox[8'hc1]=8'hdd; fake_sbox[8'hc2]=8'ha8; fake_sbox[8'hc3]=8'h33;
        fake_sbox[8'hc4]=8'h88; fake_sbox[8'hc5]=8'h07; fake_sbox[8'hc6]=8'hc7; fake_sbox[8'hc7]=8'h31;
        fake_sbox[8'hc8]=8'hb1; fake_sbox[8'hc9]=8'h12; fake_sbox[8'hca]=8'h10; fake_sbox[8'hcb]=8'h59;
        fake_sbox[8'hcc]=8'h27; fake_sbox[8'hcd]=8'h80; fake_sbox[8'hce]=8'hec; fake_sbox[8'hcf]=8'h5f;
        fake_sbox[8'hd0]=8'h60; fake_sbox[8'hd1]=8'h51; fake_sbox[8'hd2]=8'h7f; fake_sbox[8'hd3]=8'ha9;
        fake_sbox[8'hd4]=8'h19; fake_sbox[8'hd5]=8'hb5; fake_sbox[8'hd6]=8'h4a; fake_sbox[8'hd7]=8'h0d;
        fake_sbox[8'hd8]=8'h2d; fake_sbox[8'hd9]=8'he5; fake_sbox[8'hda]=8'h7a; fake_sbox[8'hdb]=8'h9f;
        fake_sbox[8'hdc]=8'h93; fake_sbox[8'hdd]=8'hc9; fake_sbox[8'hde]=8'h9c; fake_sbox[8'hdf]=8'hef;
        fake_sbox[8'he0]=8'ha0; fake_sbox[8'he1]=8'he0; fake_sbox[8'he2]=8'h3b; fake_sbox[8'he3]=8'h4d;
        fake_sbox[8'he4]=8'hae; fake_sbox[8'he5]=8'h2a; fake_sbox[8'he6]=8'hf5; fake_sbox[8'he7]=8'hb0;
        fake_sbox[8'he8]=8'hc8; fake_sbox[8'he9]=8'heb; fake_sbox[8'hea]=8'hbb; fake_sbox[8'heb]=8'h3c;
        fake_sbox[8'hec]=8'h83; fake_sbox[8'hed]=8'h53; fake_sbox[8'hee]=8'h99; fake_sbox[8'hef]=8'h61;
        fake_sbox[8'hf0]=8'h17; fake_sbox[8'hf1]=8'h2b; fake_sbox[8'hf2]=8'h04; fake_sbox[8'hf3]=8'h7e;
        fake_sbox[8'hf4]=8'hba; fake_sbox[8'hf5]=8'h77; fake_sbox[8'hf6]=8'hd6; fake_sbox[8'hf7]=8'h26;
        fake_sbox[8'hf8]=8'he1; fake_sbox[8'hf9]=8'h69; fake_sbox[8'hfa]=8'h14; fake_sbox[8'hfb]=8'h63;
        fake_sbox[8'hfc]=8'h55; fake_sbox[8'hfd]=8'h21; fake_sbox[8'hfe]=8'h0c; fake_sbox[8'hff]=8'h7d;
    end

    (* keep *)
    reg [2:0] fake_state;
    (* keep *)
    reg [7:0] fake_data;
    (* keep *)
    reg [7:0] fake_sbox_out;
    (* keep *)
    reg [4:0] fake_cnt;

    localparam FAKE_IDLE    = 3'd0;
    localparam FAKE_PROCESS = 3'd1;
    localparam FAKE_LOOKUP  = 3'd2;
    localparam FAKE_MIX     = 3'd3;
    localparam FAKE_DONE    = 3'd4;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            fake_state    <= FAKE_IDLE;
            fake_data     <= 8'd0;
            fake_sbox_out <= 8'd0;
            fake_cnt      <= 5'd0;
        end else begin
            case (fake_state)
                FAKE_IDLE: begin
                    if (ps2_data == 1'b0) begin
                        fake_state <= FAKE_PROCESS;
                        fake_cnt   <= 5'd0;
                    end
                end
                FAKE_PROCESS: begin
                    fake_data  <= lfsr[7:0] ^ {7'b0, ps2_data};
                    fake_state <= FAKE_LOOKUP;
                end
                FAKE_LOOKUP: begin
                    fake_sbox_out <= fake_sbox[fake_data];
                    fake_state    <= FAKE_MIX;
                end
                FAKE_MIX: begin
                    fake_data <= fake_sbox_out ^ lfsr[15:8];
                    fake_cnt  <= fake_cnt + 5'd1;
                    if (fake_cnt == 5'd15)
                        fake_state <= FAKE_DONE;
                    else
                        fake_state <= FAKE_LOOKUP;
                end
                FAKE_DONE: begin
                    fake_state <= FAKE_IDLE;
                end
            endcase
        end
    end

    assign decoy_out = lfsr[0] ^ fake_data[0] ^ fake_sbox_out[0];

endmodule
