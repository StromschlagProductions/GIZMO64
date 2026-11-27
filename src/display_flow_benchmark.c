/* Real PAL-cycle conversation workload, shared by release and bitmap UI. */
#include <stdio.h>
#include "ui.h"
#include "link.h"

static unsigned int ticks(void)
{
    return ((unsigned int)*(volatile unsigned char *)0x00a1 << 8) |
           *(volatile unsigned char *)0x00a2;
}

int main(void)
{
    static const char response[]=
        "THE OLD OBSERVATORY ABOVE THE HARBOR HELD A QUIET VIEW OF THE NIGHT SKY.";
    char input[121],report[40];
    unsigned char i;
    unsigned int start,key_ticks,line_ticks,max_line=0,all_ticks,next;
    ui_init();
    link_state=LINK_ONLINE;
    ui_status_changed();
    input[0]=0;
    ui_prompt(input);
    start=ticks();
    while ((unsigned int)(ticks()-start)<3) {link_tick();ui_tick(0);}
    start=ticks();
    for (i=0;i<90;++i) {
        input[i]=(i%7)==6 ? ' ' : 'A'+(i%26);
        input[i+1]=0;
        ui_prompt(input);
        link_tick();
        ui_tick(0);
    }
    key_ticks=ticks()-start;
    ui_submit(input);
    input[0]=0;ui_prompt(input);
    ui_gizmo_start();
    start=ticks();next=start;
    ui_line(""); /* BEGIN frame inserts the same separator as the real link. */
    for (i=0;i<24;++i) {
        /* About 17 jiffies per 70-byte frame: the 2400-baud receive budget. */
        while ((short)(ticks()-next)<0) {link_tick();ui_tick(1);}
        {
            unsigned int begun=ticks();
            ui_gizmo(response);
            line_ticks=ticks()-begun;
            if (line_ticks>max_line) max_line=line_ticks;
        }
        next+=17;
    }
    ui_line(""); /* END frame. */
    all_ticks=ticks()-start;
    ui_service_toggle();
    ui_system("SYNTHETIC PAL CONVERSATION / 24 FRAMES");
    sprintf(report,"90 KEYS: %u TICKS",key_ticks);ui_system(report);
    sprintf(report,"24 FRAMES: %u TICKS",all_ticks);ui_system(report);
    sprintf(report,"SLOWEST FRAME: %u TICKS",max_line);ui_system(report);
#ifdef GIZMO_TEXT_DIAG
    {
        extern const unsigned char display_assets[3776];
        volatile unsigned char *sprites=(volatile unsigned char *)0x8800;
        volatile unsigned char *pointers=(volatile unsigned char *)0x87f8;
        unsigned int bad=0,j;
        for (j=0;j<704;++j)
            if (sprites[j]!=display_assets[3072+j]) ++bad;
        sprintf(report,"SPRITE BYTES WRONG: %u",bad);ui_system(report);
        sprintf(report,"POINTERS: %u %u %u",pointers[0],pointers[1],pointers[7]);ui_system(report);
    }
#endif
    for (;;) {link_tick();ui_tick(0);}
}
