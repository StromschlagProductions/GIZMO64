#include <assert.h>
#include "ui.h"
#include "link.h"

unsigned char ui_test_cell(unsigned char x, unsigned char y);
unsigned char ui_test_sprite(unsigned char frame, unsigned char offset);
unsigned char ui_test_register(unsigned int address);
void ui_test_set_register(unsigned int address, unsigned char value);
unsigned char link_state = LINK_OFFLINE;
char link_host[16] = "192.168.178.244";
const char *link_state_name(void) { return link_state == LINK_ONLINE ? "ONLINE" : "OFFLINE"; }
void link_poll(void) { }

int main(void)
{
    unsigned char i;
    ui_init();
    assert(ui_test_cell(2, 0) == (7 | 0x80));
    assert(ui_test_cell(0, 4) == 32);
    assert(ui_test_cell(3, 0) == (9 | 0x80));
    assert(ui_test_cell(1, 24) == 6);
    assert(ui_test_register(0xd018) == 0x14);
    assert(ui_test_register(0x07f8) == 0xe0);
    assert(ui_test_register(0xd015) == 3);
    assert(ui_test_register(0xd010) == 3);
    assert(ui_test_register(0x07f9) == 0xe1);
    assert((ui_test_register(0xdd00) & 3) == 3);
    assert((ui_test_register(0xdd02) & 3) == 3);
    assert((ui_test_register(0xd011) & 0x70) == 0x10);
    for (i = 0; i < 4; ++i) {
        unsigned char j, x, y, left = 0, right = 0;
        for (j = 0; j < 63; ++j) {
            left |= ui_test_sprite(i, j);
            right |= ui_test_sprite(i, j + 64);
        }
        assert(left && right);
        for (x = 0; x < 48; ++x) {
            unsigned char found = 0;
            for (y = 0; y < 21; ++y) {
                unsigned char offset = (x >= 24 ? 64 : 0) + y * 3 + (x % 24) / 8;
                found |= ui_test_sprite(i, offset) & (0x80 >> (x & 7));
            }
            assert(found);
        }
    }
    assert(ui_test_cell(0, 5) == 32);
    ui_test_set_register(0xd012, 255);
    ui_tick(0);
    ui_test_set_register(0xd012, 0);
    ui_tick(0);
    assert(ui_test_cell(1, 2) == 12);
    assert(ui_test_cell(8, 2) == 15);
    link_state = LINK_ONLINE;
    ui_test_set_register(0xd012, 255);
    ui_tick(0);
    ui_test_set_register(0xd012, 0);
    ui_tick(0);
    assert(ui_test_cell(8, 2) == 15);
    assert(ui_test_cell(9, 2) == 14);
    for (i = 0; i < 16; ++i) {
        ui_test_set_register(0xd012, 255); ui_tick(0);
        ui_test_set_register(0xd012, 0); ui_tick(0);
    }
    assert(ui_test_register(0x07f8) == 0xe2);
    assert(ui_test_register(0x07f9) == 0xe3);
    ui_clear();
    ui_text("\xc1\xc2\xc3");
    assert(ui_test_cell(0, 5) == 1);
    assert(ui_test_cell(1, 5) == 2);
    ui_clear();
    ui_text("12345678901234567890123456789012345 ABCDE");
    assert(ui_test_cell(34, 5) == '5');
    assert(ui_test_cell(35, 5) == 32);
    assert(ui_test_cell(0, 6) == 1);
    assert(ui_test_cell(4, 6) == 5);
    ui_clear();
    ui_text("1234567890123456789012345678901234567890");
    ui_input_char('X');
    assert(ui_test_cell(0, 6) == 24);
    ui_clear();
    for (i = 0; i < 25; ++i) ui_line("TEST");
    assert(ui_test_cell(2, 0) == (7 | 0x80));
    assert(ui_test_cell(0, 4) == 32);
    assert(ui_test_cell(0, 21) == 20);
    assert(ui_test_cell(1, 24) == 6);
    return 0;
}
