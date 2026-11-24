#include <assert.h>
#include "ui.h"

unsigned char link_test_text_to_wire(unsigned char c);
unsigned char link_test_wire_to_text(unsigned char c);
void ui_line(const char *text) { (void)text; }
void ui_system(const char *text) { (void)text; }
void ui_gizmo(const char *text) { (void)text; }
void ui_status_changed(void) { }

int main(void)
{
    assert(link_test_text_to_wire(0xc1) == 0x41);
    assert(link_test_text_to_wire(0xd4) == 0x54);
    assert(link_test_text_to_wire('9') == '9');
    assert(link_test_wire_to_text(0x41) == 0xc1);
    assert(link_test_wire_to_text(0x5a) == 0xda);
    assert(link_test_wire_to_text(0x0d) == 0x0d);
    return 0;
}
