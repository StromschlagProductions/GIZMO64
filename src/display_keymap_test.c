/* Show a red border on any keyboard layout mapping failure. */
#include "ui.h"
#include "ui_bitmap.h"

int main(void)
{
    volatile unsigned char *border=(volatile unsigned char *)0xd020;
    ui_init();
    if (ui_keyboard_layout()!=0 || ui_keyboard_map('Y')!='Y') *border=2;
    ui_help_toggle();
    ui_menu_move(1);ui_menu_move(1);ui_menu_activate();
    if (ui_keyboard_layout()!=1 ||
        ui_keyboard_map('Y')!='Z' || ui_keyboard_map('Z')!='Y' ||
        ui_keyboard_map('y')!='z' || ui_keyboard_map('z')!='y' ||
        ui_keyboard_map(0xd9)!=0xda || ui_keyboard_map(0xda)!=0xd9 ||
        ui_keyboard_map('A')!='A') *border=2;
    for (;;) ui_tick(0);
}
