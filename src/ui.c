#include <string.h>
#include "ui.h"
#include "link.h"
#include "header_art.h"

#define HISTORY_LINES 112
#define DIALOG_ROWS 17
#define DIALOG_TOP 4

#ifdef GIZMO_TEST
static unsigned char test_screen[1000], test_colors[1000], test_sprites[512];
static unsigned char test_border, test_background, test_sid;
static unsigned char test_registers[65536];
#define SCREEN test_screen
#define COLORS test_colors
#define BORDER test_border
#define BACKGROUND test_background
#define SPRITES test_sprites
#define SID_VOICE test_sid
#define REGISTER(a) test_registers[a]
#else
#define SCREEN ((volatile unsigned char *)0x6400)
#define COLORS ((volatile unsigned char *)0xd800)
#define BORDER (*(volatile unsigned char *)0xd020)
#define BACKGROUND (*(volatile unsigned char *)0xd021)
#define SPRITES ((volatile unsigned char *)0x7800)
#define SID_VOICE (*(volatile unsigned char *)0xd404)
#define REGISTER(a) (*(volatile unsigned char *)(a))
extern const unsigned char gizmo_font[2048];
#endif

static const unsigned char palettes[2] = {5, 3};
static const unsigned char accents[2] = {13, 14};
static unsigned char palette;
static unsigned char history[HISTORY_LINES][40];
static unsigned char history_start, history_count, view_start, live = 1;
static unsigned char draft[40], draft_col, gizmo_first = 1;
static unsigned char waiting, service, sound_enabled;
static unsigned char memory_count = 255;
static unsigned char service_lines[8][40], service_start, service_count;
static unsigned char pulse, phase, previous_raster = 255;
static unsigned char sound_ticks, cursor_on, cursor_x, cursor_y;
static unsigned char last_state = 255;
static const char *editor_text = "";
static const unsigned char wave[24] = {
    10,10,10,9,8,6,4,3,5,8,10,11,12,14,16,17,15,12,10,9,10,10,10,10
};

static unsigned char screen_code(unsigned char c)
{
    if (c >= 0xc1 && c <= 0xda) return c - 0xc0;
    if (c >= 0x61 && c <= 0x7a) c -= 32;
    if (c >= 0x41 && c <= 0x5a) return c - 64;
    if (c >= 32 && c <= 95) return c;
    return 63;
}

static void raw_cell(unsigned char x, unsigned char y, unsigned char code, unsigned char color)
{
    unsigned int offset;
    if (x >= 40 || y >= 25) return;
    offset = (unsigned int)y * 40 + x;
    SCREEN[offset] = code;
    COLORS[offset] = color;
}

static void cell(unsigned char x, unsigned char y, unsigned char c, unsigned char color)
{
    raw_cell(x, y, screen_code(c), color);
}

static void print_at(unsigned char x, unsigned char y, const char *text, unsigned char color)
{
    while (*text && x < 40) cell(x++, y, *text++, color);
}

static void clear_row(unsigned char y, unsigned char color)
{
    unsigned char x;
    for (x = 0; x < 40; ++x) {
        raw_cell(x, y, 32, color);
        if ((x & 7) == 0) link_poll();
    }
}

static void draw_header(void)
{
    unsigned char x, y;
    for (y = 0; y < 3; ++y) {
        for (x = 0; x < 40; ++x) {
            raw_cell(x, y, gizmo_header[(unsigned int)y * 40 + x], accents[palette]);
            if ((x & 7) == 0) link_poll();
        }
    }
}

static void draw_status(void)
{
    clear_row(3, palettes[palette]);
    if (service) print_at(0, 3, "SERVICE MODE / F8 CLOSE", accents[palette]);
    else if (!live) print_at(0, 3,
        history_count > view_start + DIALOG_ROWS ? "SCROLLBACK / NEW LINES / F7 LIVE" :
        "SCROLLBACK / F7 LIVE", accents[palette]);
    else if (link_state == LINK_ONLINE) print_at(0, 3, "READY", accents[palette]);
    else if (link_state == LINK_OFFLINE || link_state == LINK_ERROR)
        print_at(0, 3, "SYSTEM UNAVAILABLE", accents[palette]);
    else print_at(0, 3, "INITIALIZING", accents[palette]);
}

static void draw_footer(void)
{
    clear_row(21, accents[palette]);
    print_at(0, 21, "----------------------------------------", accents[palette]);
    clear_row(24, accents[palette]);
    if (service) print_at(0, 24, "F8 CLOSE  DIAG  HEX  IP  SOUND", accents[palette]);
    else print_at(0, 24, "F1 COLOR F3 BACK F5 NEXT F7 LIVE", accents[palette]);
}

static unsigned char slot(unsigned char logical)
{
    unsigned char index = history_start + logical;
    if (index >= HISTORY_LINES) index -= HISTORY_LINES;
    return index;
}

static void draw_dialog(void)
{
    unsigned char y, x, logical, index;
    for (y = 0; y < DIALOG_ROWS; ++y) {
        logical = view_start + y;
        if (logical >= history_count) { clear_row(DIALOG_TOP + y, palettes[palette]); continue; }
        index = slot(logical);
        for (x = 0; x < 40; ++x) {
            raw_cell(x, DIALOG_TOP + y, history[index][x], palettes[palette]);
            if ((x & 7) == 0) link_poll();
        }
    }
    draw_status();
}

static void draw_service(void)
{
    unsigned char y, x, index;
    char count[4];
    for (y = 4; y <= 20; ++y) clear_row(y, palettes[palette]);
    print_at(1, 4, "SERVICE // LINK DIAGNOSTICS", accents[palette]);
    print_at(1, 5, "STATE: ", palettes[palette]);
    print_at(8, 5, link_state_name(), palettes[palette]);
    print_at(1, 6, "HOST: ", palettes[palette]);
    print_at(7, 6, link_host, palettes[palette]);
    print_at(23, 6, "PORT: 6464", palettes[palette]);
    print_at(1, 7, "ACIA: $DE00  2400 BAUD", palettes[palette]);
    print_at(1, 8, "MEMORIES: ", palettes[palette]);
    if (memory_count != 255) {
        count[0] = '0' + memory_count / 100;
        count[1] = '0' + (memory_count / 10) % 10;
        count[2] = '0' + memory_count % 10;
        count[3] = 0;
        print_at(11, 8, count, palettes[palette]);
    }
    for (y = 0; y < service_count; ++y) {
        index = service_start + y;
        if (index >= 8) index -= 8;
        for (x = 0; x < 40; ++x) raw_cell(x, 11 + y, service_lines[index][x], palettes[palette]);
        link_poll();
    }
    draw_status();
}

static void redraw(void)
{
    draw_header();
    if (service) draw_service(); else draw_dialog();
    draw_footer();
}

static void commit(void)
{
    unsigned char x, index;
    if (history_count == HISTORY_LINES) {
        if (!live && view_start) --view_start;
        ++history_start;
        if (history_start == HISTORY_LINES) history_start = 0;
        index = slot(HISTORY_LINES - 1);
    } else {
        index = slot(history_count);
        ++history_count;
    }
    for (x = 0; x < 40; ++x) history[index][x] = x < draft_col ? draft[x] : 32;
    draft_col = 0;
    if (live) view_start = history_count > DIALOG_ROWS ? history_count - DIALOG_ROWS : 0;
    if (service) draw_status(); else draw_dialog();
}

static void put_char(unsigned char c)
{
    if (c == '\n') { commit(); return; }
    if (draft_col == 40) commit();
    draft[draft_col++] = screen_code(c);
    link_poll();
}

void ui_text(const char *text)
{
    unsigned char length;
    while (*text) {
        if (*text == '\n') { commit(); ++text; continue; }
        if (*text == ' ') { put_char(' '); ++text; continue; }
        length = 0;
        while (text[length] && text[length] != ' ' && text[length] != '\n' && length < 40) ++length;
        if (draft_col && draft_col + length > 40) commit();
        while (length--) put_char(*text++);
    }
}

void ui_line(const char *text) { ui_text(text); commit(); }
void ui_submit(const char *text) { ui_text("YOU: "); ui_line(text); }

void ui_gizmo(const char *text)
{
    if (gizmo_first) ui_text("GZM: ");
    else ui_text("     ");
    ui_line(text);
    gizmo_first = 0;
}

void ui_gizmo_start(void) { gizmo_first = 1; }

void ui_system(const char *text)
{
    unsigned char x, index, length;
    if (!service) {
        if (link_state == LINK_ONLINE && (strstr(text,"TIMEOUT") || strstr(text,"FEHL") || strstr(text,"UNVOLL") ||
            strstr(text,"OVERRUN") || strstr(text,"UEBERLAUF") || strstr(text,"ABBRUCH") ||
            strstr(text,"NICHT VERFUEGBAR")))
            ui_line("SYSTEM UNAVAILABLE");
        return;
    }
    if (service_count == 8) {
        ++service_start; if (service_start == 8) service_start = 0;
        index = service_start + 7; if (index >= 8) index -= 8;
    } else {
        index = service_start + service_count;
        if (index >= 8) index -= 8;
        ++service_count;
    }
    length = (unsigned char)strlen(text);
    for (x = 0; x < 40; ++x) service_lines[index][x] = x < length ? screen_code(text[x]) : 32;
    draw_service();
}

void ui_clear(void)
{
    history_start = history_count = view_start = draft_col = 0;
    live = 1; gizmo_first = 1;
    redraw();
}

void ui_scroll_back(void)
{
    if (service || history_count <= DIALOG_ROWS) return;
    if (live) { live = 0; view_start = history_count > DIALOG_ROWS ? history_count - DIALOG_ROWS : 0; }
    view_start = view_start > 9 ? view_start - 9 : 0;
    draw_dialog();
}

void ui_scroll_next(void)
{
    unsigned char end;
    if (service || live) return;
    end = history_count > DIALOG_ROWS ? history_count - DIALOG_ROWS : 0;
    if (view_start + 9 >= end) { live = 1; view_start = end; }
    else view_start += 9;
    draw_dialog();
}

void ui_scroll_live(void)
{
    if (service) return;
    live = 1;
    view_start = history_count > DIALOG_ROWS ? history_count - DIALOG_ROWS : 0;
    draw_dialog();
}

unsigned char ui_service_toggle(void)
{
    service = !service;
    redraw();
    return service;
}

unsigned char ui_service_active(void) { return service; }
void ui_waiting(unsigned char value) { waiting = value; }
void ui_memory_count(unsigned char count) { memory_count = count; if (service) draw_service(); }
void ui_status_changed(void) { last_state = 255; }

void ui_theme(void)
{
    palette ^= 1;
    REGISTER(0xd027) = accents[palette];
    REGISTER(0xd028) = accents[palette];
    redraw();
    ui_prompt(editor_text);
}

void ui_sound_toggle(void) { sound_enabled = !sound_enabled; }

void ui_key_sound(void)
{
    if (!sound_enabled) return;
    REGISTER(0xd400) = 90;
    REGISTER(0xd401) = 18;
    REGISTER(0xd405) = 0;
    REGISTER(0xd406) = 0x22;
    SID_VOICE = 0x11;
    sound_ticks = 2;
}

static void make_sprites(void)
{
    unsigned char frame, x, y, from, to, sample;
    unsigned int offset;
    for (frame = 0; frame < 4; ++frame) {
        for (offset = 0; offset < 128; ++offset) SPRITES[(unsigned int)frame * 128 + offset] = 0;
        for (x = 0; x < 48; ++x) {
            sample = wave[(x + frame * 2) % 24];
            from = x ? wave[(x - 1 + frame * 2) % 24] : sample;
            to = sample;
            if (from > to) { y = from; from = to; to = y; }
            for (y = from; y <= to; ++y) {
                offset = (unsigned int)frame * 128 + (unsigned int)y * 3 + (x % 24) / 8;
                if (x >= 24) offset += 64;
                SPRITES[offset] |= (unsigned char)(0x80 >> (x & 7));
            }
        }
    }
}

void ui_prompt(const char *input)
{
    unsigned char i, x, y, length, start;
    editor_text = input;
    length = (unsigned char)strlen(input);
    start = length > 74 ? length - 74 : 0;
    clear_row(22, palettes[palette]); clear_row(23, palettes[palette]);
    print_at(0, 22, "YOU: ", accents[palette]);
    x = 5; y = 22;
    for (i = start; i < length; ++i) {
        if (x == 40) { x = 0; y = 23; }
        if (y >= 24) break;
        cell(x++, y, input[i], palettes[palette]);
        if ((i & 7) == 0) link_poll();
    }
    if (x == 40) { x = 0; y = 23; }
    cursor_x = x; cursor_y = y;
    cursor_on = 0;
}

void ui_input_char(unsigned char c) { (void)c; ui_prompt(editor_text); }
void ui_input_backspace(void) { ui_prompt(editor_text); }

void ui_tick(unsigned char active)
{
    unsigned char raster = REGISTER(0xd012);
    if (raster >= previous_raster) { previous_raster = raster; return; }
    previous_raster = raster;
    if (sound_ticks && !--sound_ticks) SID_VOICE = 0x10;
    if (++pulse >= 8) {
        pulse = 0;
        if (active) phase = (phase + 1) & 3;
        else phase = 0;
        REGISTER(0x67f8) = 0xe0 + phase * 2;
        REGISTER(0x67f9) = 0xe1 + phase * 2;
    }
    if (last_state != link_state) {
        last_state = link_state;
        if (service) draw_service();
        else draw_status();
    }
    if (cursor_on) {
        cell(cursor_x, cursor_y, ' ', palettes[palette]);
        cursor_on = 0;
    } else if (!waiting || editor_text[0]) {
        raw_cell(cursor_x, cursor_y, 96, accents[palette]);
        cursor_on = 1;
    }
}

void ui_init(void)
{
    unsigned int i;
    REGISTER(0xdd02) |= 3;
    REGISTER(0xdd00) = (REGISTER(0xdd00) & 0xfc) | 2;
    REGISTER(0xd011) = (REGISTER(0xd011) & 0x9f) | 0x10;
    REGISTER(0xd016) = (REGISTER(0xd016) & 0xef) | 8;
    BORDER = BACKGROUND = 0;
    REGISTER(0xd018) = 0x9c;
#ifndef GIZMO_TEST
    for (i = 0; i < 2048; ++i) {
        ((volatile unsigned char *)0x7000)[i] = gizmo_font[i];
        if ((i & 7) == 0) link_poll();
    }
#endif
    for (i = 0; i < 1000; ++i) { SCREEN[i] = 32; COLORS[i] = palettes[palette]; }
    make_sprites();
    REGISTER(0xd015) = 3;
    REGISTER(0xd010) = 3;
    REGISTER(0xd000) = 264 - 256;
    REGISTER(0xd001) = 50;
    REGISTER(0xd002) = 288 - 256;
    REGISTER(0xd003) = 50;
    REGISTER(0xd01b) &= 0xfc;
    REGISTER(0xd01c) &= 0xfc;
    REGISTER(0xd01d) &= 0xfc;
    REGISTER(0xd017) &= 0xfc;
    REGISTER(0xd027) = accents[palette];
    REGISTER(0xd028) = accents[palette];
    REGISTER(0x67f8) = 0xe0;
    REGISTER(0x67f9) = 0xe1;
    REGISTER(0xd418) = 15;
    redraw();
    ui_prompt("");
}

#ifdef GIZMO_TEST
unsigned char ui_test_cell(unsigned char x, unsigned char y) { return SCREEN[(unsigned int)y * 40 + x]; }
unsigned char ui_test_color(unsigned char x, unsigned char y) { return COLORS[(unsigned int)y * 40 + x]; }
unsigned char ui_test_sprite(unsigned char frame, unsigned char offset) { return SPRITES[(unsigned int)frame * 128 + offset]; }
unsigned char ui_test_register(unsigned int address) { return REGISTER(address); }
void ui_test_set_register(unsigned int address, unsigned char value) { REGISTER(address) = value; }
unsigned char ui_test_history_count(void) { return history_count; }
unsigned char ui_test_view_start(void) { return view_start; }
unsigned char ui_test_live(void) { return live; }
#endif
