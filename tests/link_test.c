#include <assert.h>
#include <string.h>
#include "link.h"

void link_test_feed(const char *bytes);
void link_test_advance(unsigned int ticks);
static char last_message[128];
void ui_line(const char *message)
{
    strcpy(last_message, message);
}

static void drain_dial(void)
{
    unsigned char i;
    for (i = 0; i < 40; ++i) link_tick();
    assert(link_state == LINK_HANDSHAKE);
}

int main(void)
{
    link_init();
    assert(link_set_host("192.168.178.244"));
    assert(!link_set_host("256.1.1.1"));
    assert(!link_set_host("1.2.3"));
    assert(!link_set_host("1..2.3"));
    link_connect();
    drain_dial();
    link_test_feed("UPLINK HERGESTELLT. GIZMO ONLINE.\r\nCON");
    link_tick(); link_tick(); link_tick();
    assert(link_state == LINK_VERIFY);
    link_test_feed("NECT 2400\rPONG // GIZMO UPLINK AKTIV\r\n");
    link_tick(); link_tick(); link_tick();
    assert(link_state == LINK_ONLINE);
    link_offline();
    link_test_feed("PONG // GIZMO UPLINK AKTIV\r");
    link_tick(); link_tick();
    assert(link_state == LINK_OFFLINE);
    link_connect();
    drain_dial();
    link_test_feed("CONNECT 2400\n");
    link_tick();
    assert(link_state == LINK_VERIFY);
    link_test_feed("PONG // GIZMO UPLINK AKTIV\n");
    link_tick(); link_tick();
    assert(link_state == LINK_ONLINE);
    link_ping();
    assert(link_state == LINK_VERIFY);
    link_test_advance(251);
    link_tick();
    assert(link_state == LINK_OFFLINE);
    link_connect();
    drain_dial();
    link_test_feed("BUSY\r");
    link_tick();
    assert(link_state == LINK_ERROR);
    link_connect();
    drain_dial();
    link_test_advance(601);
    link_tick();
    assert(link_state == LINK_OFFLINE);
    return 0;
}
