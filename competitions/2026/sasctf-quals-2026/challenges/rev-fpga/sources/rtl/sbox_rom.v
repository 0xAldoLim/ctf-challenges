`timescale 1ns/1ps

module sbox_rom (
    input  wire       clk,
    input  wire [7:0] addr,
    input  wire       rd,
    output reg  [7:0] data_out
);

    reg [7:0] mem [0:255];

    initial begin
        mem[8'h00]=8'h63; mem[8'h01]=8'h7c; mem[8'h02]=8'h77; mem[8'h03]=8'h7b;
        mem[8'h04]=8'hf2; mem[8'h05]=8'h6b; mem[8'h06]=8'h6f; mem[8'h07]=8'hc5;
        mem[8'h08]=8'h30; mem[8'h09]=8'h01; mem[8'h0a]=8'h67; mem[8'h0b]=8'h2b;
        mem[8'h0c]=8'hfe; mem[8'h0d]=8'hd7; mem[8'h0e]=8'hab; mem[8'h0f]=8'h76;
        mem[8'h10]=8'hca; mem[8'h11]=8'h82; mem[8'h12]=8'hc9; mem[8'h13]=8'h7d;
        mem[8'h14]=8'hfa; mem[8'h15]=8'h59; mem[8'h16]=8'h47; mem[8'h17]=8'hf0;
        mem[8'h18]=8'had; mem[8'h19]=8'hd4; mem[8'h1a]=8'ha2; mem[8'h1b]=8'haf;
        mem[8'h1c]=8'h9c; mem[8'h1d]=8'ha4; mem[8'h1e]=8'h72; mem[8'h1f]=8'hc0;
        mem[8'h20]=8'hb7; mem[8'h21]=8'hfd; mem[8'h22]=8'h93; mem[8'h23]=8'h26;
        mem[8'h24]=8'h36; mem[8'h25]=8'h3f; mem[8'h26]=8'hf7; mem[8'h27]=8'hcc;
        mem[8'h28]=8'h34; mem[8'h29]=8'ha5; mem[8'h2a]=8'he5; mem[8'h2b]=8'hf1;
        mem[8'h2c]=8'h71; mem[8'h2d]=8'hd8; mem[8'h2e]=8'h31; mem[8'h2f]=8'h15;
        mem[8'h30]=8'h04; mem[8'h31]=8'hc7; mem[8'h32]=8'h23; mem[8'h33]=8'hc3;
        mem[8'h34]=8'h18; mem[8'h35]=8'h96; mem[8'h36]=8'h05; mem[8'h37]=8'h9a;
        mem[8'h38]=8'h07; mem[8'h39]=8'h12; mem[8'h3a]=8'h80; mem[8'h3b]=8'he2;
        mem[8'h3c]=8'heb; mem[8'h3d]=8'h27; mem[8'h3e]=8'hb2; mem[8'h3f]=8'h75;
        mem[8'h40]=8'h09; mem[8'h41]=8'h83; mem[8'h42]=8'h2c; mem[8'h43]=8'h1a;
        mem[8'h44]=8'h1b; mem[8'h45]=8'h6e; mem[8'h46]=8'h5a; mem[8'h47]=8'ha0;
        mem[8'h48]=8'h52; mem[8'h49]=8'h3b; mem[8'h4a]=8'hd6; mem[8'h4b]=8'hb3;
        mem[8'h4c]=8'h29; mem[8'h4d]=8'he3; mem[8'h4e]=8'h2f; mem[8'h4f]=8'h84;
        mem[8'h50]=8'h53; mem[8'h51]=8'hd1; mem[8'h52]=8'h00; mem[8'h53]=8'hed;
        mem[8'h54]=8'h20; mem[8'h55]=8'hfc; mem[8'h56]=8'hb1; mem[8'h57]=8'h5b;
        mem[8'h58]=8'h6a; mem[8'h59]=8'hcb; mem[8'h5a]=8'hbe; mem[8'h5b]=8'h39;
        mem[8'h5c]=8'h4a; mem[8'h5d]=8'h4c; mem[8'h5e]=8'h58; mem[8'h5f]=8'hcf;
        mem[8'h60]=8'hd0; mem[8'h61]=8'hef; mem[8'h62]=8'haa; mem[8'h63]=8'hfb;
        mem[8'h64]=8'h43; mem[8'h65]=8'h4d; mem[8'h66]=8'h33; mem[8'h67]=8'h85;
        mem[8'h68]=8'h45; mem[8'h69]=8'hf9; mem[8'h6a]=8'h02; mem[8'h6b]=8'h7f;
        mem[8'h6c]=8'h50; mem[8'h6d]=8'h3c; mem[8'h6e]=8'h9f; mem[8'h6f]=8'ha8;
        mem[8'h70]=8'h51; mem[8'h71]=8'ha3; mem[8'h72]=8'h40; mem[8'h73]=8'h8f;
        mem[8'h74]=8'h92; mem[8'h75]=8'h9d; mem[8'h76]=8'h38; mem[8'h77]=8'hf5;
        mem[8'h78]=8'hbc; mem[8'h79]=8'hb6; mem[8'h7a]=8'hda; mem[8'h7b]=8'h21;
        mem[8'h7c]=8'h10; mem[8'h7d]=8'hff; mem[8'h7e]=8'hf3; mem[8'h7f]=8'hd2;
        mem[8'h80]=8'hcd; mem[8'h81]=8'h0c; mem[8'h82]=8'h13; mem[8'h83]=8'hec;
        mem[8'h84]=8'h5f; mem[8'h85]=8'h97; mem[8'h86]=8'h44; mem[8'h87]=8'h17;
        mem[8'h88]=8'hc4; mem[8'h89]=8'ha7; mem[8'h8a]=8'h7e; mem[8'h8b]=8'h3d;
        mem[8'h8c]=8'h64; mem[8'h8d]=8'h5d; mem[8'h8e]=8'h19; mem[8'h8f]=8'h73;
        mem[8'h90]=8'h60; mem[8'h91]=8'h81; mem[8'h92]=8'h4f; mem[8'h93]=8'hdc;
        mem[8'h94]=8'h22; mem[8'h95]=8'h2a; mem[8'h96]=8'h90; mem[8'h97]=8'h88;
        mem[8'h98]=8'h46; mem[8'h99]=8'hee; mem[8'h9a]=8'hb8; mem[8'h9b]=8'h14;
        mem[8'h9c]=8'hde; mem[8'h9d]=8'h5e; mem[8'h9e]=8'h0b; mem[8'h9f]=8'hdb;
        mem[8'ha0]=8'he0; mem[8'ha1]=8'h32; mem[8'ha2]=8'h3a; mem[8'ha3]=8'h0a;
        mem[8'ha4]=8'h49; mem[8'ha5]=8'h06; mem[8'ha6]=8'h24; mem[8'ha7]=8'h5c;
        mem[8'ha8]=8'hc2; mem[8'ha9]=8'hd3; mem[8'haa]=8'hac; mem[8'hab]=8'h62;
        mem[8'hac]=8'h91; mem[8'had]=8'h95; mem[8'hae]=8'he4; mem[8'haf]=8'h79;
        mem[8'hb0]=8'he7; mem[8'hb1]=8'hc8; mem[8'hb2]=8'h37; mem[8'hb3]=8'h6d;
        mem[8'hb4]=8'h8d; mem[8'hb5]=8'hd5; mem[8'hb6]=8'h4e; mem[8'hb7]=8'ha9;
        mem[8'hb8]=8'h6c; mem[8'hb9]=8'h56; mem[8'hba]=8'hf4; mem[8'hbb]=8'hea;
        mem[8'hbc]=8'h65; mem[8'hbd]=8'h7a; mem[8'hbe]=8'hae; mem[8'hbf]=8'h08;
        mem[8'hc0]=8'hba; mem[8'hc1]=8'h78; mem[8'hc2]=8'h25; mem[8'hc3]=8'h2e;
        mem[8'hc4]=8'h1c; mem[8'hc5]=8'ha6; mem[8'hc6]=8'hb4; mem[8'hc7]=8'hc6;
        mem[8'hc8]=8'he8; mem[8'hc9]=8'hdd; mem[8'hca]=8'h74; mem[8'hcb]=8'h1f;
        mem[8'hcc]=8'h4b; mem[8'hcd]=8'hbd; mem[8'hce]=8'h8b; mem[8'hcf]=8'h8a;
        mem[8'hd0]=8'h70; mem[8'hd1]=8'h3e; mem[8'hd2]=8'hb5; mem[8'hd3]=8'h66;
        mem[8'hd4]=8'h48; mem[8'hd5]=8'h03; mem[8'hd6]=8'hf6; mem[8'hd7]=8'h0e;
        mem[8'hd8]=8'h61; mem[8'hd9]=8'h35; mem[8'hda]=8'h57; mem[8'hdb]=8'hb9;
        mem[8'hdc]=8'h86; mem[8'hdd]=8'hc1; mem[8'hde]=8'h1d; mem[8'hdf]=8'h9e;
        mem[8'he0]=8'he1; mem[8'he1]=8'hf8; mem[8'he2]=8'h98; mem[8'he3]=8'h11;
        mem[8'he4]=8'h69; mem[8'he5]=8'hd9; mem[8'he6]=8'h8e; mem[8'he7]=8'h94;
        mem[8'he8]=8'h9b; mem[8'he9]=8'h1e; mem[8'hea]=8'h87; mem[8'heb]=8'he9;
        mem[8'hec]=8'hce; mem[8'hed]=8'h55; mem[8'hee]=8'h28; mem[8'hef]=8'hdf;
        mem[8'hf0]=8'h8c; mem[8'hf1]=8'ha1; mem[8'hf2]=8'h89; mem[8'hf3]=8'h0d;
        mem[8'hf4]=8'hbf; mem[8'hf5]=8'he6; mem[8'hf6]=8'h42; mem[8'hf7]=8'h68;
        mem[8'hf8]=8'h41; mem[8'hf9]=8'h99; mem[8'hfa]=8'h2d; mem[8'hfb]=8'h0f;
        mem[8'hfc]=8'hb0; mem[8'hfd]=8'h54; mem[8'hfe]=8'hbb; mem[8'hff]=8'h16;
    end

    always @(posedge clk) begin
        if (rd)
            data_out <= mem[addr];
    end

endmodule
