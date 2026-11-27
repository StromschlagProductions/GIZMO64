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
#ifdef GIZMO_TEXT_CHECK
    {
        extern const unsigned char display_assets[3776];
        volatile unsigned char *sprites=(volatile unsigned char *)0x8800;
        volatile unsigned char *pointers=(volatile unsigned char *)0x87f8;
        unsigned int j;
        for (j=0;j<704;++j)
            if (sprites[j]!=display_assets[3072+j])
                *(volatile unsigned char *)0xd020=2;
        for (j=0;j<7;++j)
            if (pointers[j]!=0x20+j)
                *(volatile unsigned char *)0xd020=2;
    }
#endif
    for (;;) ui_tick(0);
}
