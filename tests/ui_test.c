#include <assert.h>
#include "ui.h"

unsigned char ui_test_cell(unsigned char x, unsigned char y);
void link_poll(void) { }

int main(void)
{
    unsigned char i;
    ui_init();
    assert(ui_test_cell(0, 0) == 3);
    assert(ui_test_cell(0, 4) == 32);
    ui_clear();
    ui_text("12345678901234567890123456789012345 ABCDE");
    assert(ui_test_cell(34, 5) == '5');
    assert(ui_test_cell(35, 5) == 32);
    assert(ui_test_cell(0, 6) == 1);
    assert(ui_test_cell(4, 6) == 5);
    ui_clear();
    for (i = 0; i < 25; ++i) ui_line("TEST");
    assert(ui_test_cell(0, 0) == 3);
    assert(ui_test_cell(0, 4) == 32);
    assert(ui_test_cell(0, 23) == 20);
    return 0;
}
