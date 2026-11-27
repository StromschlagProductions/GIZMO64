#include <assert.h>
#include <stdio.h>
#include "ui.h"
#include "link.h"

unsigned char ui_test_cell(unsigned char x, unsigned char y);
unsigned char ui_test_color(unsigned char x, unsigned char y);
unsigned char ui_test_sprite(unsigned char frame, unsigned char offset);
unsigned char ui_test_register(unsigned int address);
void ui_test_set_register(unsigned int address, unsigned char value);
unsigned char ui_test_history_count(void);
unsigned char ui_test_view_start(void);
unsigned char ui_test_live(void);
unsigned char link_state = LINK_MODEM;
char link_host[16] = "192.168.178.244";
static unsigned int polls;
const char *link_state_name(void) { return link_state == LINK_ONLINE ? "ONLINE" : "OFFLINE"; }
void link_poll(void) { ++polls; }

static void frame(unsigned char active)
{
    ui_test_set_register(0xd012,255); ui_tick(active);
    ui_test_set_register(0xd012,0); ui_tick(active);
}

int main(void)
{
    unsigned int i, before;
    unsigned char old_top, old_editor, prior_view;
    char line[40];
    ui_init();
    ui_scroll_back();
    assert(ui_test_live()); /* no false scrollback on an empty archive */
    assert(ui_test_cell(7,0)>=128 && ui_test_cell(23,0)>=128);
    assert(ui_test_cell(10,1)>=128 && ui_test_cell(20,1)>=128);
    assert(ui_test_cell(7,2)>=128 && ui_test_cell(23,2)>=128);
    assert(ui_test_cell(0,3)==9); /* INITIALIZING below the logo */
    assert(ui_test_cell(0,24)==6); /* F1 COLOR */
    assert(ui_test_color(0,4)==5 && ui_test_color(0,1)==13);
    assert(ui_test_register(0xd018)==0x9c);
    assert((ui_test_register(0xdd00)&3)==2);
    assert((ui_test_register(0xdd02)&3)==3);
    assert((ui_test_register(0xd011)&0x70)==0x10);
    assert(ui_test_register(0xd015)==3 && ui_test_register(0xd010)==3);
    assert(ui_test_register(0x67f8)==0xe0 && ui_test_register(0x67f9)==0xe1);
    for (i=0;i<4;++i) {
        unsigned char j, left=0,right=0;
        for (j=0;j<63;++j) { left|=ui_test_sprite(i,j); right|=ui_test_sprite(i,j+64); }
        assert(left && right);
    }
    ui_theme();
    assert(ui_test_color(0,4)==3 && ui_test_color(0,1)==14);
    ui_theme();
    assert(ui_test_color(0,4)==5 && ui_test_color(0,1)==13);
    ui_theme();
    assert(ui_test_color(0,4)==3); /* no third palette */
    ui_theme();
    link_state=LINK_ONLINE;frame(0);
    for (i=0;i<40;++i) assert(ui_test_cell(i,3)==32); /* clear gap when online */
    for (i=0;i<8;++i) frame(1);
    assert(ui_test_register(0x67f8)==0xe2 && ui_test_register(0x67f9)==0xe3);
    for (i=0;i<8;++i) frame(0);
    assert(ui_test_register(0x67f8)==0xe0);

    ui_prompt("DRAFT KEPT WHILE SCROLLING");
    old_editor=ui_test_cell(5,22);
    for (i=0;i<130;++i) {
        sprintf(line,"ROW%03u WITH TEXT?",i);
        ui_line(line);
    }
    assert(ui_test_history_count()==112 && ui_test_live());
    assert(ui_test_view_start()==95);
    assert(ui_test_cell(5,22)==old_editor);
    before=polls;
    ui_scroll_back();
    assert(!ui_test_live() && ui_test_view_start()==86);
    old_top=ui_test_cell(6,4);
    prior_view=ui_test_view_start();
    ui_line("NEW INCOMING WHILE READING");
    assert(ui_test_view_start()==prior_view-1);
    assert(ui_test_cell(6,4)==old_top);
    assert(ui_test_cell(5,22)==old_editor);
    assert(polls>before); /* redraw yields to ACIA receive */
    ui_scroll_next();
    assert(ui_test_view_start()==prior_view-1+9);
    ui_scroll_live();
    assert(ui_test_live() && ui_test_view_start()==95);
    assert(ui_test_cell(0,20)==14); /* newest line starts with N */
    ui_scroll_back();
    ui_scroll_next();
    assert(ui_test_live());

    ui_clear();
    ui_submit("HELLO, GIZMO?");
    assert(ui_test_cell(0,4)==25 && ui_test_cell(5,4)==8);
    ui_gizmo_start();
    ui_gizmo("HELLO AGAIN. THIS IS A LONG RESPONSE WITH PUNCTUATION!");
    assert(ui_test_history_count()>=3);
    ui_line("");
    assert(ui_test_history_count()>=4);
    ui_prompt("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789012345678901234567890123456789");
    assert(ui_test_cell(5,22)!=32 && ui_test_cell(0,23)!=32);

    before=ui_test_history_count();
    ui_system("ATDT 192.168.178.244:6464");
    assert(ui_test_history_count()==before); /* technical chatter hidden */
    ui_system("TIMEOUT / PONG FEHLT");
    assert(ui_test_history_count()==before+1);
    assert(ui_test_cell(0,20)!=0); /* neutral error, never raw modem text */
    assert(ui_service_toggle());
    assert(ui_test_cell(1,6)==8); /* HOST */
    ui_system("RX:12 TX:5 ST:10");
    assert(ui_test_cell(0,11)==18); /* RX in service only */
    assert(!ui_service_toggle());
    assert(ui_test_cell(0,11)!=18); /* service log removed from dialogue */
    assert(ui_test_history_count()==before+1);
    return 0;
}
