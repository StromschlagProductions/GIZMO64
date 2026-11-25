#include <string.h>
#include <stdio.h>
#include <stdlib.h>
#include "link.h"
#include "ui.h"

#ifdef GIZMO_TEST
static unsigned char test_data, test_status = 16, test_command, test_control;
static unsigned int test_time;
static unsigned char test_tx[128], test_tx_length;
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
unsigned char link_waiting;
static unsigned char response_started, pending_active, pending_index;
static char pending_text[121];
static unsigned int response_deadline;

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
static unsigned char available;
static unsigned char retry_pending, saw_connect, saw_greeting;
static unsigned int rx_since_dial, overrun_at_dial;
static unsigned char last_status, overrun_latched, hex_position;
static unsigned char hex_bytes[16];
static unsigned int received_bytes, sent_bytes, overrun_count, drop_count;


static unsigned char wire_to_text(unsigned char c)
{
#if defined(__CC65__) || defined(GIZMO_PETSCII_TEST)
    if (c >= 0x61 && c <= 0x7a) c -= 32;
    if (c >= 0x41 && c <= 0x5a) return c + 128;
#endif
    return c;
}

static unsigned char text_to_wire(unsigned char c)
{
#if defined(__CC65__) || defined(GIZMO_PETSCII_TEST)
    if (c >= 0xc1 && c <= 0xda) return c - 128;
#endif
    return c;
}

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

static void disconnect(unsigned char retry)
{
    COMMAND = 0x0a;
    tx_head = tx_tail;
    retry_pending = retry;
    link_state = LINK_HANGUP;
    link_waiting = pending_active = response_started = 0;
    ui_waiting(0);
    timeout(2);
}

void link_poll(void)
{
    unsigned char status;
    unsigned char next;
    if (!available) return;
    status = STATUS;
    last_status = status;
    if (status & 4) {
        if (!overrun_latched) { ++overrun_count; link_overruns = 1; }
        overrun_latched = 1;
    } else overrun_latched = 0;
    if (status & 8) {
        unsigned char c = DATA;
        ++received_bytes;
        ++rx_since_dial;
        hex_bytes[hex_position++ & 15] = c;
        next = (rx_head + 1) & 127;
        if (next == rx_tail) { link_drops = 1; ++drop_count; }
        else { rx[rx_head] = c; rx_head = next; }
    }
    if (tx_tail != tx_head && (STATUS & 16)) {
        DATA = tx[tx_tail];
        ++sent_bytes;
#ifdef GIZMO_TEST
        if (test_tx_length < sizeof(test_tx)) test_tx[test_tx_length++] = DATA;
#endif
        tx_tail = (tx_tail + 1) & 63;
    }
}

static void send(const char *s)
{
    unsigned char next;
    while (*s) {
        next = (tx_head + 1) & 63;
        if (next == tx_tail) { link_drops = 1; ++drop_count; return; }
        tx[tx_head] = text_to_wire(*s++);
        tx_head = next;
    }
}

static void send_cr(void)
{
    unsigned char next = (tx_head + 1) & 63;
    if (next == tx_tail) { link_drops = 1; ++drop_count; return; }
    tx[tx_head] = 13;
    tx_head = next;
}

static void ping(void)
{
    send("PING"); send_cr();
    link_state = LINK_VERIFY;
    timeout(5);
    ui_system("PING AN PC-BRUECKE");
}

static void received_line(void)
{
    line[line_length] = 0;
    if (!line_length) return;
    if (link_state == LINK_OFFLINE || link_state == LINK_ERROR ||
        link_state == LINK_HANGUP) return;
    if (strcmp(line, "[[GIZMO:BEGIN]]") == 0) {
        response_started = 1;
        ui_line("");
        ui_gizmo_start();
        send("ACK"); send_cr();
        return;
    }
    if (strcmp(line, "[[GIZMO:END]]") == 0) {
        response_started = link_waiting = 0;
        ui_waiting(0);
        ui_key_sound();
        ui_line("");
        send("ACK"); send_cr();
        return;
    }
    if (response_started) {
        if (strcmp(line, "[[GIZMO:PARA]]") == 0) ui_line("");
        else ui_gizmo(line);
        send("ACK"); send_cr();
        return;
    }
    if (strncmp(line, "FACTS: ", 7) == 0) {
        ui_memory_count((unsigned char)atoi(line + 7));
        return;
    }
    if (link_state != LINK_ONLINE) ui_system(line);
    if (strcmp(line, "PONG // GIZMO UPLINK AKTIV") == 0 && link_state == LINK_VERIFY) {
        link_state = LINK_ONLINE;
        ui_system("UPLINK VERIFIZIERT");
        send("STATUS"); send_cr();
    } else if (strncmp(line, "CONNECT", 7) == 0) {
        saw_connect = 1;
        if (link_state == LINK_DIAL || link_state == LINK_HANDSHAKE) ping();
    } else if (strcmp(line, "UPLINK HERGESTELLT. GIZMO ONLINE.") == 0) {
        saw_greeting = 1;
        if (link_state == LINK_DIAL || link_state == LINK_HANDSHAKE) ping();
    } else if (strncmp(line, "NO CARRIER", 10) == 0 ||
               strncmp(line, "BUSY", 4) == 0 ||
               strcmp(line, "ERROR") == 0) {
        if (link_waiting) {
            ui_system("GIZMO / ANTWORT UNTERBROCHEN");
            link_waiting = pending_active = response_started = 0;
            ui_waiting(0);
        }
        link_state = LINK_ERROR;
        ui_system("MODEM: VERBINDUNG FEHLGESCHLAGEN");
    }
}

unsigned char link_send_text(const char *text)
{
    if (link_state != LINK_ONLINE || link_waiting || pending_active ||
        strlen(text) > 120) return 0;
    strcpy(pending_text, text);
    pending_index = 0;
    pending_active = link_waiting = 1;
    ui_waiting(1);
    return 1;
}

void link_tick(void)
{
    unsigned char c;
    unsigned char quota = 16;
    link_poll();
    while (pending_active && pending_text[pending_index] &&
           ((tx_head + 1) & 63) != tx_tail) {
        tx[tx_head] = text_to_wire(pending_text[pending_index++]);
        tx_head = (tx_head + 1) & 63;
    }
    if (pending_active && !pending_text[pending_index] &&
        ((tx_head + 1) & 63) != tx_tail) {
        send_cr();
        pending_active = 0;
        response_deadline = now() + (unsigned int)150 * tick_rate;
    }
    while (rx_tail != rx_head && quota--) {
        c = rx[rx_tail];
        rx_tail = (rx_tail + 1) & 127;
        if (link_waiting && !pending_active)
            response_deadline = now() + (unsigned int)150 * tick_rate;
        if (c == 13 || c == 10) {
            if (c == 10 && last_cr) { last_cr = 0; continue; }
            last_cr = (c == 13);
            if (!line_discard) received_line();
            line_length = 0;
            line_discard = 0;
        } else {
            last_cr = 0;
            if (!line_discard && c >= 32 && c <= 126) {
                if (line_length < 80) line[line_length++] = wire_to_text(c);
                else { link_drops = 1; ++drop_count; line_length = 0; line_discard = 1; }
            }
        }
        link_poll();
    }
    if (link_overruns) { link_overruns = 0; ui_system("WARNUNG: ACIA OVERRUN"); }
    if (link_drops) { link_drops = 0; ui_system("WARNUNG: PUFFERUEBERLAUF"); }
    if (link_state == LINK_DIAL && tx_head == tx_tail) {
        link_state = LINK_HANDSHAKE;
        timeout(12);
    }
    if ((link_state == LINK_HANDSHAKE || link_state == LINK_VERIFY) && expired()) {
        if (overrun_count != overrun_at_dial) ui_system("TIMEOUT / ACIA OVERRUN");
        else if (!rx_since_dial) ui_system("TIMEOUT / KEINE RX-DATEN");
        else if (!saw_connect) ui_system("TIMEOUT / CONNECT FEHLT");
        else ui_system("TIMEOUT / PONG FEHLT");
        disconnect(0);
    }
    if (link_state == LINK_HANGUP && expired()) {
        link_state = LINK_OFFLINE;
        if (retry_pending) link_connect();
        else ui_system("MODEM GETRENNT / OFFLINE");
    }
    if (link_waiting && !pending_active && (short)(now() - response_deadline) >= 0) {
        link_waiting = response_started = 0;
        ui_waiting(0);
        ui_system("GIZMO / ANTWORT UNVOLLSTAENDIG");
        disconnect(1);
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
    COMMAND = 0x0b;
    available = (CONTROL == 0x18 && COMMAND == 0x0b);
    link_state = available ? LINK_MODEM : LINK_OFFLINE;
}

void link_connect(void)
{
    if (!available) { ui_system("ACIA $DE00 NICHT VERFUEGBAR"); return; }
    if (link_state == LINK_HANGUP) { retry_pending = 1; return; }
    if (link_state == LINK_DIAL || link_state == LINK_HANDSHAKE ||
        link_state == LINK_VERIFY || link_state == LINK_ONLINE ||
        link_state == LINK_ERROR) { disconnect(1); return; }
    rx_head = rx_tail = tx_head = tx_tail = line_length = line_discard = 0;
    rx_since_dial = saw_connect = saw_greeting = 0;
    overrun_at_dial = overrun_count;
    COMMAND = 0x0b;
    send("ATDT "); send(link_host); send(":6464"); send_cr();
    link_state = LINK_DIAL;
    ui_system("WAHLE PC-UPLINK...");
}

void link_offline(void)
{
    if (available) disconnect(0);
    tx_head = tx_tail = rx_head = rx_tail = line_length = line_discard = 0;
    if (!available) link_state = LINK_OFFLINE;
    link_waiting = pending_active = response_started = 0;
    ui_waiting(0);
    ui_system("OFFLINE-MODUS AKTIV");
}

void link_ping(void)
{
    if (link_state == LINK_HANDSHAKE || link_state == LINK_VERIFY ||
        link_state == LINK_ONLINE) ping();
    else ui_system("PING: ZUERST UPLINK WAEHLEN");
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
    ui_status_changed();
    return 1;
}

const char *link_state_name(void)
{
    static const char *names[] = {"OFFLINE", "MODEM", "WAHL", "HANDSHAKE",
        "PING", "ONLINE", "FEHLER", "TRENNEN"};
    return names[link_state];
}

void link_diagnostics(void)
{
    char text[40];
    sprintf(text, "RX:%u TX:%u ST:%02X", received_bytes, sent_bytes, last_status);
    ui_system(text);
    sprintf(text, "OV:%u DROP:%u C:%u G:%u", overrun_count, drop_count,
            saw_connect, saw_greeting);
    ui_system(text);
}

void link_hex_dump(void)
{
    unsigned char i, count = hex_position < 16 ? hex_position : 16;
    char text[40];
    static const char digits[] = "0123456789ABCDEF";
    ui_system("HEX / LETZTE RX-BYTES");
    for (i = 0; i < count; ++i) {
        unsigned char value = hex_bytes[(hex_position - count + i) & 15];
        text[i * 2] = digits[value >> 4];
        text[i * 2 + 1] = digits[value & 15];
    }
    text[count * 2] = 0;
    ui_system(text);
}

#ifdef GIZMO_TEST
void link_test_feed(const char *bytes)
{
    while (*bytes) {
        unsigned char next = (rx_head + 1) & 127;
        ++received_bytes;
        ++rx_since_dial;
        hex_bytes[hex_position++ & 15] = *bytes;
        if (next == rx_tail) link_drops = 1;
        else { rx[rx_head] = *bytes; rx_head = next; }
        ++bytes;
    }
}
void link_test_advance(unsigned int ticks) { test_time += ticks; }
unsigned char link_test_text_to_wire(unsigned char c) { return text_to_wire(c); }
unsigned char link_test_wire_to_text(unsigned char c) { return wire_to_text(c); }
unsigned char link_test_tx_length(void) { return test_tx_length; }
unsigned char link_test_tx(unsigned char index) { return test_tx[index]; }
void link_test_tx_reset(void) { test_tx_length = 0; }
unsigned char link_test_command(void) { return COMMAND; }
void link_test_status(unsigned char status) { test_status = status; }
unsigned int link_test_drop_count(void) { return drop_count; }
unsigned int link_test_overrun_count(void) { return overrun_count; }
#endif
