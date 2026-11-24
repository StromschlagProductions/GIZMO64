#include <string.h>
#include "link.h"
#include "ui.h"

#ifdef GIZMO_TEST
static unsigned char test_data, test_status = 16, test_command, test_control;
static unsigned int test_time;
#define DATA test_data
#define STATUS test_status
#define COMMAND test_command
#define CONTROL test_control
#else
#define DATA (*(volatile unsigned char *)0xde00)
#define STATUS (*(volatile unsigned char *)0xde01)
#define COMMAND (*(volatile unsigned char *)0xde02)
#define CONTROL (*(volatile unsigned char *)0xde03)
#endif

unsigned char link_state = LINK_OFFLINE;
unsigned char link_overruns;
unsigned char link_drops;
char link_host[16] = "192.168.178.244";

static unsigned char rx[128];
static unsigned char rx_head, rx_tail;
static char tx[64];
static unsigned char tx_head, tx_tail;
static char line[81];
static unsigned char line_length;
static unsigned char line_discard;
static unsigned char last_cr;
static unsigned int deadline;
static unsigned char tick_rate;

static unsigned int now(void)
{
#ifdef GIZMO_TEST
    return test_time;
#else
    return ((unsigned int)*(volatile unsigned char *)0x00a1 << 8) |
        *(volatile unsigned char *)0x00a2;
#endif
}

static void timeout(unsigned char seconds)
{
    deadline = now() + (unsigned int)seconds * tick_rate;
}

static unsigned char expired(void)
{
    return (short)(now() - deadline) >= 0;
}

void link_poll(void)
{
    unsigned char status = STATUS;
    unsigned char next;
    if (status & 4) link_overruns = 1;
    if (status & 8) {
        unsigned char c = DATA;
        next = (rx_head + 1) & 127;
        if (next == rx_tail) link_drops = 1;
        else { rx[rx_head] = c; rx_head = next; }
    }
    if (tx_tail != tx_head && (STATUS & 16)) {
        DATA = tx[tx_tail];
        tx_tail = (tx_tail + 1) & 63;
    }
}

static void send(const char *s)
{
    unsigned char next;
    while (*s) {
        next = (tx_head + 1) & 63;
        if (next == tx_tail) { link_drops = 1; return; }
        tx[tx_head] = *s++;
        tx_head = next;
    }
}

static void ping(void)
{
    send("PING\r");
    link_state = LINK_VERIFY;
    timeout(5);
    ui_line("PING AN PC-BRUECKE");
}

static void received_line(void)
{
    line[line_length] = 0;
    if (!line_length) return;
    if (link_state == LINK_OFFLINE || link_state == LINK_ERROR) return;
    if (strcmp(line, "PONG // GIZMO UPLINK AKTIV") == 0 && link_state == LINK_VERIFY) {
        link_state = LINK_ONLINE;
        ui_line("UPLINK VERIFIZIERT");
    } else if (strncmp(line, "CONNECT", 7) == 0 ||
               strcmp(line, "UPLINK HERGESTELLT. GIZMO ONLINE.") == 0) {
        if (link_state == LINK_DIAL || link_state == LINK_HANDSHAKE) ping();
        ui_line(line);
    } else if (strncmp(line, "NO CARRIER", 10) == 0 ||
               strncmp(line, "BUSY", 4) == 0 ||
               strcmp(line, "ERROR") == 0) {
        link_state = LINK_ERROR;
        ui_line("MODEM: VERBINDUNG FEHLGESCHLAGEN");
    } else if (link_state == LINK_ONLINE) {
        ui_line(line);
    }
}

void link_tick(void)
{
    unsigned char c;
    unsigned char quota = 16;
    link_poll();
    while (rx_tail != rx_head && quota--) {
        c = rx[rx_tail];
        rx_tail = (rx_tail + 1) & 127;
        if (c == '\r' || c == '\n') {
            if (c == '\n' && last_cr) { last_cr = 0; continue; }
            last_cr = (c == '\r');
            if (!line_discard) received_line();
            line_length = 0;
            line_discard = 0;
        } else {
            last_cr = 0;
            if (!line_discard && c >= 32 && c <= 126) {
                if (line_length < 80) line[line_length++] = c;
                else { link_drops = 1; line_length = 0; line_discard = 1; }
            }
        }
        link_poll();
    }
    if (link_overruns) { link_overruns = 0; ui_line("WARNUNG: ACIA OVERRUN"); }
    if (link_drops) { link_drops = 0; ui_line("WARNUNG: PUFFERUEBERLAUF"); }
    if (link_state == LINK_DIAL && tx_head == tx_tail) {
        link_state = LINK_HANDSHAKE;
        timeout(12);
    }
    if ((link_state == LINK_HANDSHAKE || link_state == LINK_VERIFY) && expired()) {
        link_state = LINK_OFFLINE;
        ui_line("UPLINK TIMEOUT - OFFLINE");
    }
}

void link_init(void)
{
    rx_head = rx_tail = tx_head = tx_tail = line_length = line_discard = 0;
#ifdef GIZMO_TEST
    tick_rate = 50;
#else
    tick_rate = (*(volatile unsigned char *)0x02a6) ? 60 : 50;
#endif
    CONTROL = 0x18;
    COMMAND = 0x03;
    link_state = LINK_MODEM;
}

void link_connect(void)
{
    if (link_state == LINK_DIAL || link_state == LINK_HANDSHAKE ||
        link_state == LINK_VERIFY || link_state == LINK_ONLINE) link_offline();
    rx_head = rx_tail = tx_head = tx_tail = line_length = line_discard = 0;
    COMMAND = 0x03;
    send("ATDT "); send(link_host); send(":6464\r");
    link_state = LINK_DIAL;
    ui_line("WAHLE PC-UPLINK...");
}

void link_offline(void)
{
    COMMAND = 0x02;
    tx_head = tx_tail = rx_head = rx_tail = line_length = line_discard = 0;
    link_state = LINK_OFFLINE;
    ui_line("OFFLINE-MODUS AKTIV");
}

void link_ping(void)
{
    if (link_state == LINK_ONLINE) ping();
    else ui_line("KEIN VERIFIZIERTER UPLINK");
}

unsigned char link_set_host(const char *host)
{
    unsigned char dots = 0, digits = 0;
    unsigned int octet = 0;
    const char *p = host;
    if (!*p) return 0;
    while (*p) {
        if (*p == '.') {
            if (!digits || octet > 255 || dots == 3) return 0;
            ++dots; digits = 0; octet = 0;
        } else if (*p >= '0' && *p <= '9') {
            if (++digits > 3) return 0;
            octet = octet * 10 + *p - '0';
        } else return 0;
        ++p;
    }
    if (dots != 3 || !digits || octet > 255 || p - host > 15) return 0;
    strcpy(link_host, host);
    return 1;
}

const char *link_state_name(void)
{
    static const char *names[] = {"OFFLINE", "MODEM", "WAHL", "HANDSHAKE",
        "PING", "ONLINE", "FEHLER"};
    return names[link_state];
}

#ifdef GIZMO_TEST
void link_test_feed(const char *bytes)
{
    while (*bytes) {
        unsigned char next = (rx_head + 1) & 127;
        if (next == rx_tail) link_drops = 1;
        else { rx[rx_head] = *bytes; rx_head = next; }
        ++bytes;
    }
}
void link_test_advance(unsigned int ticks) { test_time += ticks; }
#endif
