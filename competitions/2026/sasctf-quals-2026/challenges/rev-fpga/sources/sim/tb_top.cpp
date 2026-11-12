#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <vector>
#include "Vtop.h"
#include "verilated.h"
#include "ps2_driver.h"

#define MAX_SIM_CYCLES 5000000

int main(int argc, char** argv) {
    Verilated::commandArgs(argc, argv);

    const char* flag = nullptr;
    if (argc > 1) {
        flag = argv[1];
    } else {
        fprintf(stderr, "Usage: %s <flag_string>\n", argv[0]);
        return 1;
    }

    Vtop* top = new Vtop;
    PS2Driver ps2(500);

    top->CLK = 0;
    top->RST_N = 0;
    top->PS2_CLK = 1;
    top->PS2_DATA = 1;

    for (int i = 0; i < 20; i++) {
        top->CLK = !top->CLK;
        top->eval();
    }
    top->RST_N = 1;

    int flag_len = strlen(flag);
    for (int i = 0; i < flag_len; i++) {
        ps2.send_char(flag[i]);
    }
    ps2.send_enter();

    std::vector<uint8_t> output_bytes;
    uint64_t cycle = 0;
    bool done = false;

    while (cycle < MAX_SIM_CYCLES && !done) {
        top->CLK = 1;
        top->PS2_CLK = ps2.get_ps2_clk();
        top->PS2_DATA = ps2.get_ps2_data();
        top->eval();

        if (top->LED_STROBE) {
            output_bytes.push_back(top->LED & 0xFF);
        }

        top->CLK = 0;
        top->eval();

        ps2.tick();
        cycle++;

        if (!ps2.busy() && cycle > 100000) {
            static uint64_t last_strobe_cycle = 0;
            if (top->LED_STROBE)
                last_strobe_cycle = cycle;
            if (last_strobe_cycle > 0 && (cycle - last_strobe_cycle) > 5000) {
                done = true;
            }
        }
    }

    for (size_t i = 0; i < output_bytes.size(); i++) {
        printf("%02X", output_bytes[i]);
        if ((i + 1) % 8 == 0)
            printf("\n");
    }
    if (output_bytes.size() % 8 != 0)
        printf("\n");

    delete top;
    return 0;
}
