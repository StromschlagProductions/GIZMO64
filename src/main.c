#include <conio.h>
#include <string.h>
#include "ui.h"
#include "link.h"

static char input[121];
static unsigned char input_length;

static void service_command(void)
{
    if (strcmp(input,"HELP") == 0) {
        ui_system("STATUS DIAG HEX IP [ADDRESS]");
        ui_system("UPLINK OFFLINE PING CLS SOUND");
    } else if (strcmp(input,"STATUS") == 0) {
        ui_system(link_state_name());
        link_diagnostics();
    } else if (strcmp(input,"DIAG") == 0) link_diagnostics();
    else if (strcmp(input,"HEX") == 0) link_hex_dump();
    else if (strcmp(input,"IP") == 0) ui_system(link_host);
    else if (strncmp(input,"IP ",3) == 0) {
        if (link_set_host(input + 3)) ui_system("HOST ADDRESS SET");
        else ui_system("INVALID IPV4 ADDRESS");
    } else if (strcmp(input,"UPLINK") == 0) link_connect();
    else if (strcmp(input,"OFFLINE") == 0) link_offline();
    else if (strcmp(input,"PING") == 0) link_ping();
    else if (strcmp(input,"SOUND") == 0) { ui_sound_toggle(); ui_system("SOUND OPTION CHANGED"); }
    else if (strcmp(input,"CLS") == 0) ui_clear();
    else if (input[0]) ui_system("UNKNOWN SERVICE COMMAND");
}

static void execute(void)
{
    if (!input_length) return;
    if (ui_service_active()) service_command();
    else if (strcmp(input,"CLS") == 0) ui_clear();
    else if (strcmp(input,"DIAG") == 0 || strcmp(input,"HEX") == 0 ||
             strcmp(input,"STATUS") == 0 || strcmp(input,"PING") == 0 ||
             strcmp(input,"UPLINK") == 0 || strcmp(input,"OFFLINE") == 0 ||
             strcmp(input,"IP") == 0 || strncmp(input,"IP ",3) == 0 ||
             strcmp(input,"HELP") == 0) ui_line("F8 SERVICE");
    else {
        ui_submit(input);
        if (link_state == LINK_ONLINE) {
            if (!link_send_text(input)) ui_line("SYSTEM BUSY");
        } else ui_line("SYSTEM UNAVAILABLE");
    }
    input_length = 0;
    input[0] = 0;
    ui_prompt(input);
}

static void keyboard(void)
{
    unsigned char c;
    if (!kbhit()) return;
    c = cgetc();
    if (c == 0x85) { ui_theme(); return; }       /* F1 */
    if (c == 0x86) { ui_scroll_back(); return; } /* F3 */
    if (c == 0x87) { ui_scroll_next(); return; } /* F5 */
    if (c == 0x88) { ui_scroll_live(); return; } /* F7 */
    if (c == 0x8c) {                            /* F8 */
        if (ui_service_toggle()) link_diagnostics();
        ui_prompt(input);
        return;
    }
    ui_key_sound();
    if (c == 13) {
        if (!link_waiting || ui_service_active()) execute();
        return;
    }
    if (c == 20 || c == 8) {
        if (input_length) {
            input[--input_length] = 0;
            ui_prompt(input);
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
    ui_prompt(input);
}

int main(void)
{
    ui_init();
    link_init();
    link_connect();
    ui_prompt(input);
    for (;;) {
        link_tick();
        keyboard();
        ui_tick(link_state == LINK_DIAL || link_state == LINK_HANDSHAKE ||
                link_state == LINK_VERIFY || link_waiting);
    }
}
