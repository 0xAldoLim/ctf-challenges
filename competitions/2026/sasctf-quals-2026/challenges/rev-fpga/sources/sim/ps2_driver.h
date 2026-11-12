#ifndef PS2_DRIVER_H
#define PS2_DRIVER_H

#include <cstdint>
#include <map>
#include <vector>
#include <cctype>

class PS2Driver {
public:
    PS2Driver(int clk_divider = 500)
        : clk_div_(clk_divider), bit_idx_(0), sending_(false),
          ps2_clk_(1), ps2_data_(1), cycle_cnt_(0), half_period_(clk_divider/2) {
        init_scancode_map();
    }

    void send_char(char c) {
        bool need_shift = false;
        uint8_t sc = get_scancode(c, need_shift);
        if (sc == 0) return;

        if (need_shift) {
            queue_frame(0x12);
        }
        queue_frame(sc);
        queue_break(sc);
        if (need_shift) {
            queue_break(0x12);
        }
    }

    void send_enter() {
        queue_frame(0x5A);
        queue_break(0x5A);
    }

    void tick() {
        if (!sending_ && !frames_.empty()) {
            current_frame_ = frames_.front();
            frames_.erase(frames_.begin());
            bit_idx_ = 0;
            cycle_cnt_ = 0;
            sending_ = true;
        }

        if (sending_) {
            cycle_cnt_++;

            if (cycle_cnt_ == 1) {
                ps2_data_ = (current_frame_ >> bit_idx_) & 1;
                ps2_clk_ = 0;
            } else if (cycle_cnt_ == half_period_) {
                ps2_clk_ = 1;
            } else if (cycle_cnt_ >= clk_div_) {
                cycle_cnt_ = 0;
                bit_idx_++;
                if (bit_idx_ >= 11) {
                    sending_ = false;
                    ps2_clk_ = 1;
                    ps2_data_ = 1;
                }
            }
        }
    }

    uint8_t get_ps2_clk() const { return ps2_clk_; }
    uint8_t get_ps2_data() const { return ps2_data_; }
    bool busy() const { return sending_ || !frames_.empty(); }

private:
    int clk_div_;
    int half_period_;
    int bit_idx_;
    int cycle_cnt_;
    bool sending_;
    uint8_t ps2_clk_;
    uint8_t ps2_data_;
    uint16_t current_frame_;
    std::vector<uint16_t> frames_;

    std::map<char, uint8_t> unshifted_map_;
    std::map<char, uint8_t> shifted_map_;

    void init_scancode_map() {
        unshifted_map_['a'] = 0x1C; unshifted_map_['b'] = 0x32;
        unshifted_map_['c'] = 0x21; unshifted_map_['d'] = 0x23;
        unshifted_map_['e'] = 0x24; unshifted_map_['f'] = 0x2B;
        unshifted_map_['g'] = 0x34; unshifted_map_['h'] = 0x33;
        unshifted_map_['i'] = 0x43; unshifted_map_['j'] = 0x3B;
        unshifted_map_['k'] = 0x42; unshifted_map_['l'] = 0x4B;
        unshifted_map_['m'] = 0x3A; unshifted_map_['n'] = 0x31;
        unshifted_map_['o'] = 0x44; unshifted_map_['p'] = 0x4D;
        unshifted_map_['q'] = 0x15; unshifted_map_['r'] = 0x2D;
        unshifted_map_['s'] = 0x1B; unshifted_map_['t'] = 0x2C;
        unshifted_map_['u'] = 0x3C; unshifted_map_['v'] = 0x2A;
        unshifted_map_['w'] = 0x1D; unshifted_map_['x'] = 0x22;
        unshifted_map_['y'] = 0x35; unshifted_map_['z'] = 0x1A;
        unshifted_map_['0'] = 0x45; unshifted_map_['1'] = 0x16;
        unshifted_map_['2'] = 0x1E; unshifted_map_['3'] = 0x26;
        unshifted_map_['4'] = 0x25; unshifted_map_['5'] = 0x2E;
        unshifted_map_['6'] = 0x36; unshifted_map_['7'] = 0x3D;
        unshifted_map_['8'] = 0x3E; unshifted_map_['9'] = 0x46;
        unshifted_map_[' '] = 0x29;
        unshifted_map_['-'] = 0x4E; unshifted_map_['='] = 0x55;
        unshifted_map_['['] = 0x54; unshifted_map_[']'] = 0x5B;
        unshifted_map_[';'] = 0x4C; unshifted_map_['\''] = 0x52;
        unshifted_map_[','] = 0x41; unshifted_map_['.'] = 0x49;
        unshifted_map_['/'] = 0x4A; unshifted_map_['\\'] = 0x5D;
        unshifted_map_['`'] = 0x0E;

        for (char c = 'A'; c <= 'Z'; c++) {
            shifted_map_[c] = unshifted_map_[c - 'A' + 'a'];
        }

        shifted_map_['{'] = 0x54;
        shifted_map_['}'] = 0x5B;
        shifted_map_['_'] = 0x4E;
        shifted_map_['+'] = 0x55;
        shifted_map_['!'] = 0x16;
        shifted_map_['@'] = 0x1E;
        shifted_map_['#'] = 0x26;
        shifted_map_['$'] = 0x25;
        shifted_map_['%'] = 0x2E;
        shifted_map_['^'] = 0x36;
        shifted_map_['&'] = 0x3D;
        shifted_map_['*'] = 0x3E;
        shifted_map_['('] = 0x46;
        shifted_map_[')'] = 0x45;
        shifted_map_[':'] = 0x4C;
        shifted_map_['"'] = 0x52;
        shifted_map_['<'] = 0x41;
        shifted_map_['>'] = 0x49;
        shifted_map_['?'] = 0x4A;
        shifted_map_['|'] = 0x5D;
        shifted_map_['~'] = 0x0E;
    }

    uint8_t get_scancode(char c, bool &need_shift) {
        need_shift = false;
        auto it = unshifted_map_.find(c);
        if (it != unshifted_map_.end())
            return it->second;
        auto it2 = shifted_map_.find(c);
        if (it2 != shifted_map_.end()) {
            need_shift = true;
            return it2->second;
        }
        return 0;
    }

    void queue_frame(uint8_t scan_code) {
        uint16_t frame = 0;
        frame |= ((uint16_t)scan_code) << 1;
        int ones = 0;
        for (int i = 0; i < 8; i++)
            if ((scan_code >> i) & 1) ones++;
        uint8_t parity = (ones % 2 == 0) ? 1 : 0;
        frame |= ((uint16_t)parity) << 9;
        frame |= (1 << 10);
        frames_.push_back(frame);
    }

    void queue_break(uint8_t scan_code) {
        queue_frame(0xF0);
        queue_frame(scan_code);
    }
};

#endif
