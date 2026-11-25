#include <conio.h>
#include <string.h>
#include "ui.h"
#include "link.h"

static char input[121];
static unsigned char input_length;
static unsigned char offline_response;
static unsigned char prompt_deferred;
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
        ui_line("MERKE: TEXT / ERINNERE / FREITEXT");
        ui_line("DIAG HEX CLS IP [ADRESSE] F1:FARBE");
    } else if (strcmp(input, "STATUS") == 0) {
        ui_text("LINK: "); ui_line(link_state_name());
        ui_text("ZIEL: "); ui_line(link_host);
        link_diagnostics();
    } else if (strcmp(input, "UPLINK") == 0) link_connect();
    else if (strcmp(input, "PING") == 0) link_ping();
    else if (strcmp(input, "DIAG") == 0) link_diagnostics();
    else if (strcmp(input, "HEX") == 0) link_hex_dump();
    else if (strcmp(input, "OFFLINE") == 0) link_offline();
    else if (strcmp(input, "CLS") == 0) ui_clear();
    else if (strcmp(input, "IP") == 0) ui_line(link_host);
    else if (strncmp(input, "IP ", 3) == 0) {
        if (link_set_host(input + 3)) ui_line("ZIELADRESSE GESETZT");
        else ui_line("UNGUELTIGE IPV4-ADRESSE");
    } else if (!input[0]) { }
    else if (link_state == LINK_OFFLINE || link_state == LINK_ERROR) {
        ui_gizmo_start();
        ui_gizmo(offline_messages[offline_response]);
        offline_response = (offline_response + 1) % 3;
    } else if (link_state == LINK_ONLINE) {
        if (link_send_text(input)) prompt_deferred = 1;
        else ui_system("GIZMO ANTWORTET NOCH");
    } else ui_line("UPLINK NICHT BEREIT.");
    input_length = 0;
    input[0] = 0;
    if (!prompt_deferred) ui_prompt(input);
}

static void keyboard(void)
{
    unsigned char c;
    if (!kbhit()) return;
    c = cgetc();
    ui_key_sound();
    if (c == 0x85) { ui_theme(); return; }
    if (link_waiting && c == 13) return;
    if (c == 13) { execute(); return; }
    if (c == 20 || c == 8) {
        if (input_length) {
            input[--input_length] = 0;
            if (!link_waiting) ui_input_backspace();
        }
        return;
    }
#ifdef __CC65__
    if (c >= 0x41 && c <= 0x5a) c += 128;
    if (!((c >= 0xc1 && c <= 0xda) || (c >= 32 && c <= 64) ||
          (c >= 91 && c <= 95))) return;
#else
    if (c >= 'a' && c <= 'z') c -= 32;
    if (c < 32 || c > 126) return;
#endif
    if (input_length >= 120) return;
    input[input_length++] = c;
    input[input_length] = 0;
    if (!link_waiting) ui_input_char(c);
}

int main(void)
{
    ui_init();
    ui_system("BOOT / GIZMO-64 0.2.2");
    ui_system("VIDEO + AUDIO / BEREIT");
    link_init();
    ui_system("ACIA $DE00 / PRUEFUNG");
    ui_system("NETZ / VERBINDUNG WIRD GEPRUEFT");
    link_connect();
    ui_prompt(input);
    for (;;) {
        link_tick();
        if (prompt_deferred && !link_waiting) {
            prompt_deferred = 0;
            ui_prompt(input);
        }
        keyboard();
        ui_tick(link_state == LINK_DIAL || link_state == LINK_VERIFY || link_waiting);
    }
}
