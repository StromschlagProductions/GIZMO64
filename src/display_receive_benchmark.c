/* Feed the unchanged framed RX/ACK parser at 2400-baud pacing in x64sc. */
#include <stdio.h>
#include "ui.h"
#include "link.h"

extern void flow_test_begin(void);
extern void flow_test_feed(unsigned char c);
extern unsigned int flow_test_drop_count(void),flow_test_ack_bytes(void);

static unsigned int ticks(void)
{
    return ((unsigned int)*(volatile unsigned char *)0x00a1 << 8) |
           *(volatile unsigned char *)0x00a2;
}

int main(void)
{
    static const char begin[]="[[GIZMO:BEGIN]]";
    static const char response[]=
        "THE OLD OBSERVATORY ABOVE THE HARBOR HELD A QUIET VIEW OF THE NIGHT SKY.";
    static const char end[]="[[GIZMO:END]]";
    char input[121],report[40];
    const char *segment=begin;
    unsigned char i,frame=0,position=0;
    unsigned int start,next,key_ticks,total,drain;
    ui_init();flow_test_begin();
    input[0]=0;ui_prompt(input);
    start=ticks();
    while ((unsigned int)(ticks()-start)<3) {link_tick();ui_tick(0);}
    start=ticks();
    for (i=0;i<90;++i) {
        input[i]=(i%7)==6 ? ' ' : 'A'+(i%26);
        input[i+1]=0;ui_prompt(input);link_tick();ui_tick(0);
    }
    key_ticks=ticks()-start;
    ui_submit(input);input[0]=0;ui_prompt(input);
    link_send_text("SYNTHETIC QUESTION");
    start=ticks();
    while ((unsigned int)(ticks()-start)<5) {link_tick();ui_tick(1);}
    start=ticks();next=start;
    while (frame<26) {
        if ((short)(ticks()-next)>=0) {
            for (i=0;i<4 && frame<26;++i) {
                if (segment[position]) flow_test_feed(segment[position++]);
                else {
                    flow_test_feed(13);
                    ++frame;position=0;
                    segment=frame==25 ? end : response;
                }
            }
            ++next;
        }
        link_tick();ui_tick(1);
    }
    drain=ticks();
    while (link_waiting && (unsigned int)(ticks()-drain)<120) {
        link_tick();ui_tick(1);
    }
    total=ticks()-start;
    ui_service_toggle();
    ui_system("SYNTHETIC RX / 24 FRAMES / ACK");
    sprintf(report,"90 KEYS: %u TICKS",key_ticks);ui_system(report);
    sprintf(report,"RX TOTAL: %u TICKS",total);ui_system(report);
    sprintf(report,"DROP: %u",flow_test_drop_count());ui_system(report);
    sprintf(report,"ACK BYTES: %u",flow_test_ack_bytes());ui_system(report);
#ifdef GIZMO_TEXT_DIAG
    {
        extern const unsigned char display_assets[3776];
        volatile unsigned char *sprites=(volatile unsigned char *)0x8800;
        volatile unsigned char *pointers=(volatile unsigned char *)0x87f8;
        unsigned int j,bad=0;
        for (j=0;j<704;++j) if (sprites[j]!=display_assets[3072+j]) ++bad;
        sprintf(report,"SPRITE BAD: %u",bad);ui_system(report);
        sprintf(report,"PTR: %u %u %u",pointers[0],pointers[1],pointers[7]);ui_system(report);
        sprintf(report,"BANK/D018: %u %u",
            *(volatile unsigned char *)0xdd00&3,
            *(volatile unsigned char *)0xd018);ui_system(report);
    }
#endif
    for (;;) {link_tick();ui_tick(0);}
}
