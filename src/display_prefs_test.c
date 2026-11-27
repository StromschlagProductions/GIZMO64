/* Isolated emulator harness for settings on a writable device 8. */
#include "ui.h"
#include "ui_bitmap.h"
#include "link.h"

int main(void)
{
    ui_init();
    link_state=LINK_ONLINE;
    ui_help_toggle();
#ifdef GIZMO_PREFS_WRITE
    ui_menu_activate();       /* green -> ice blue */
    ui_menu_move(1);
    ui_menu_activate();       /* standard -> compact */
    ui_menu_move(1);
    ui_menu_activate();       /* QWERTY -> QWERTZ */
    ui_menu_move(1);ui_menu_move(1);ui_menu_move(1);
    ui_menu_activate();       /* explicitly save to device 8 */
    ui_menu_move(1);       /* same selection as the fresh reader */
#endif
    for (;;) ui_tick(0);
}
