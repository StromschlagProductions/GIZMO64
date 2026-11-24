#include <assert.h>
#include <string.h>
#include "link.h"

void link_test_feed(const char *bytes);
void link_test_advance(unsigned int ticks);
unsigned char link_test_tx_length(void);
unsigned char link_test_tx(unsigned char index);
void link_test_tx_reset(void);
unsigned char link_test_command(void);
void link_test_status(unsigned char status);
static char last_message[128];
void ui_line(const char *message)
{
    strcpy(last_message, message);
}
void ui_status_changed(void) { }
void ui_waiting(unsigned char waiting) { (void)waiting; }
void ui_memory_count(unsigned char count) { (void)count; }
void ui_key_sound(void) { }
void ui_system(const char *message) { ui_line(message); }
void ui_gizmo(const char *message) { ui_line(message); }

static void drain_dial(void)
{
    unsigned char i;
    for (i = 0; i < 40; ++i) link_tick();
    assert(link_state == LINK_HANDSHAKE);
}

int main(void)
{
    link_init();
    assert(link_test_command() == 0x0b);
    assert(link_set_host("192.168.178.244"));
    assert(!link_set_host("256.1.1.1"));
    assert(!link_set_host("1.2.3"));
    assert(!link_set_host("1..2.3"));
    link_connect();
    drain_dial();
    assert(link_test_tx_length() == strlen("ATDT 192.168.178.244:6464\r"));
    assert(link_test_tx(link_test_tx_length() - 1) == 13);
    link_test_feed("UPLINK HERGESTELLT. GIZMO ONLINE.\r\nCON");
    link_tick(); link_tick(); link_tick();
    assert(link_state == LINK_VERIFY);
    link_test_feed("NECT 2400\rPONG // GIZMO UPLINK AKTIV\r\n");
    link_tick(); link_tick(); link_tick();
    assert(link_state == LINK_ONLINE);
    link_offline();
    assert(link_state == LINK_HANGUP);
    assert(link_test_command() == 0x0a);
    link_test_feed("PONG // GIZMO UPLINK AKTIV\r");
    link_tick(); link_tick();
    link_test_advance(101); link_tick();
    assert(link_state == LINK_OFFLINE);
    link_connect();
    drain_dial();
    assert(link_test_command() == 0x0b);
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
    assert(link_state == LINK_HANGUP);
    assert(strcmp(last_message, "TIMEOUT / PONG FEHLT") == 0);
    link_test_advance(101); link_tick();
    assert(link_state == LINK_OFFLINE);
    link_connect();
    drain_dial();
    link_test_feed("BUSY\r");
    link_tick();
    assert(link_state == LINK_ERROR);
    link_connect();
    assert(link_state == LINK_HANGUP);
    link_test_advance(101); link_tick();
    drain_dial();
    link_test_advance(601);
    link_tick();
    assert(strcmp(last_message, "TIMEOUT / KEINE RX-DATEN") == 0);
    link_test_advance(101); link_tick();
    assert(link_state == LINK_OFFLINE);
    link_connect();
    drain_dial();
    link_ping();
    assert(link_state == LINK_VERIFY);
    link_test_feed("PONG // GIZMO UPLINK AKTIV\r");
    link_tick(); link_tick();
    assert(link_state == LINK_ONLINE);
    link_diagnostics();
    link_hex_dump();
    link_offline(); link_test_advance(101); link_tick();
    link_connect(); drain_dial();
    link_test_feed("UPLINK HERGESTELLT. GIZMO ONLINE.\r");
    link_tick(); link_tick(); link_tick();
    assert(link_state == LINK_VERIFY);
    link_test_advance(251); link_tick();
    assert(strcmp(last_message, "TIMEOUT / CONNECT FEHLT") == 0);
    link_test_advance(101); link_tick();
    link_connect(); drain_dial();
    link_test_status(20); link_tick();
    link_test_status(16);
    link_test_advance(601); link_tick();
    assert(strcmp(last_message, "TIMEOUT / ACIA OVERRUN") == 0);
    link_test_advance(101); link_tick();
    link_connect(); drain_dial();
    link_test_feed("CONNECT 2400\r"); link_tick();
    link_test_feed("PONG // GIZMO UPLINK AKTIV\r"); link_tick(); link_tick();
    assert(link_state == LINK_ONLINE);
    { unsigned char i; for (i = 0; i < 10; ++i) link_tick(); }
    link_test_tx_reset();
    {
        char prompt[121];
        unsigned char i;
        for (i = 0; i < 120; ++i) prompt[i] = 'A';
        prompt[120] = 0;
        assert(link_send_text(prompt));
        assert(link_waiting);
        for (i = 0; i < 125; ++i) link_tick();
        assert(link_test_tx_length() == 121);
        assert(link_test_tx(120) == 13);
    }
    link_test_feed("[[GIZMO:BEGIN]]\rERSTE ZEILE\r");
    link_tick(); link_tick(); link_tick();
    link_test_feed("ZWEITE ZEILE\r[[GIZMO:END]]\r");
    link_tick(); link_tick(); link_tick();
    assert(!link_waiting);
    assert(link_state == LINK_ONLINE);
    assert(link_send_text("NOCH EIN TEST"));
    { unsigned char i; for (i = 0; i < 20; ++i) link_tick(); }
    link_test_advance(7501); link_tick();
    assert(!link_waiting);
    assert(link_state == LINK_ONLINE);
    return 0;
}
