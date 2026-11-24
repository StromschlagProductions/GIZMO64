#include <conio.h>
#include <string.h>
#include "ui.h"
#include "link.h"

static char input[39];
static unsigned char input_length;
static unsigned char offline_response;
static const char *offline_messages[] = {
    "LOKALE SYSTEME AKTIV. UPLINK RUHT.",
    "SENSORKANAL BEREIT. KEIN FERNKONTAKT.",
    "BORDKERN STABIL. WARTE AUF UPLINK."
};

static void execute(void)
{
    ui_line("");
    if (strcmp(input, "HELP") == 0) {
        ui_line("HELP STATUS UPLINK PING OFFLINE");
        ui_line("CLS IP [ADRESSE]  F1: FARBE");
    } else if (strcmp(input, "STATUS") == 0) {
        ui_text("LINK: "); ui_line(link_state_name());
        ui_text("ZIEL: "); ui_line(link_host);
    } else if (strcmp(input, "UPLINK") == 0) link_connect();
    else if (strcmp(input, "PING") == 0) link_ping();
    else if (strcmp(input, "OFFLINE") == 0) link_offline();
    else if (strcmp(input, "CLS") == 0) ui_clear();
    else if (strcmp(input, "IP") == 0) ui_line(link_host);
    else if (strncmp(input, "IP ", 3) == 0) {
        if (link_set_host(input + 3)) ui_line("ZIELADRESSE GESETZT");
        else ui_line("UNGUELTIGE IPV4-ADRESSE");
    } else if (!input[0]) { }
    else if (link_state == LINK_OFFLINE || link_state == LINK_ERROR) {
        ui_line(offline_messages[offline_response]);
        offline_response = (offline_response + 1) % 3;
    } else ui_line("UNBEKANNTER BEFEHL. HELP EINGEBEN.");
    input_length = 0;
    input[0] = 0;
    ui_prompt(input);
}

static void keyboard(void)
{
    unsigned char c;
    if (!kbhit()) return;
    c = cgetc();
    ui_key_sound();
    if (c == 0x85) { ui_theme(); return; }
    if (c == 13) { execute(); return; }
    if (c == 20 || c == 8) {
        if (input_length) { input[--input_length] = 0; ui_input_backspace(); }
        return;
    }
    if (c >= 'a' && c <= 'z') c -= 32;
    if (c >= 0xc1 && c <= 0xda) c -= 128;
    if (c < 32 || c > 126 || input_length >= 38) return;
    input[input_length++] = c;
    input[input_length] = 0;
    ui_input_char(c);
}

int main(void)
{
    ui_init();
    ui_line("GIZMO-64 // UPLINK EDITION 0.1");
    ui_line("SYSTEMKERN ONLINE");
    link_init();
    ui_line("MODEM INITIALISIERT");
    ui_line("F1: FARBE  HELP: BEFEHLE");
    link_connect();
    ui_prompt(input);
    for (;;) {
        link_tick();
        keyboard();
        ui_tick(link_state == LINK_DIAL || link_state == LINK_VERIFY ||
                link_state == LINK_ONLINE);
    }
}
