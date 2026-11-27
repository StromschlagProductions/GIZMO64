/* Synthetic C64-side timing harness. Build against either UI revision. */
#include <stdio.h>
#include "ui.h"
#include "ui_bitmap.h"
#include "link.h"

static unsigned int ticks(void)
{
    return ((unsigned int)*(volatile unsigned char *)0x00a1 << 8) |
           *(volatile unsigned char *)0x00a2;
}

int main(void)
{
    unsigned char i;
    unsigned int start, append_ticks, page_ticks, theme_ticks;
    char result[40];
    ui_init();
    link_state=LINK_ONLINE;
    ui_demo_seed();
    ui_prompt("");

    start=ticks();
    for (i=0;i<6;++i) ui_line("GZM: SYNTHETIC TIMING LINE FOR DISPLAY.");
    append_ticks=ticks()-start;

    start=ticks();
    for (i=0;i<3;++i) {ui_scroll_back();ui_scroll_live();}
    page_ticks=ticks()-start;

    start=ticks();
    for (i=0;i<2;++i) ui_theme();
    theme_ticks=ticks()-start;

    ui_service_toggle();
    ui_system("SYNTHETIC DISPLAY BENCHMARK");
    sprintf(result,"APPEND 6: %u TICKS",append_ticks);ui_system(result);
    sprintf(result,"PAGES 6: %u TICKS",page_ticks);ui_system(result);
    sprintf(result,"THEME 2: %u TICKS",theme_ticks);ui_system(result);
    for (;;) ui_tick(0);
}
