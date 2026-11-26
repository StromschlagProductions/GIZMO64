#include <string.h>
#include "ui.h"
#include "link.h"

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

static const unsigned char palettes[3] = {5, 3, 8};
static const unsigned char accents[3] = {13, 14, 7};
static unsigned char palette;
static unsigned char row = 5;
static unsigned char col;
static unsigned char cursor_on;
static unsigned char pulse;
static unsigned char sound_ticks;
static unsigned char previous_raster;
static unsigned char phase;
static unsigned char shown_state = 255;
static unsigned char editor_length, waiting, memory_count = 255;
static unsigned char gizmo_first = 1;
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

static void cell(unsigned char x, unsigned char y, unsigned char c)
{
    unsigned int offset = (unsigned int)y * 40 + x;
    if (x >= 40 || y >= 25) return;
    SCREEN[offset] = screen_code(c);
    COLORS[offset] = y == 0 || y == 24 ? accents[palette] :
        (y == 1 || y == 4 || y == 23 ? 11 : palettes[palette]);
}

static void header_status(void)
{
    const char *name = link_state_name();
    const char *label = " LINK / ";
    unsigned char x;
    for (x = 0; x < 40; ++x) cell(x, 2, ' ');
    x = 0;
    while (*label) cell(x++, 2, *label++);
    while (*name && x < 17) cell(x++, 2, *name++);
    if (memory_count != 255) {
        static const char digits[] = "0123456789";
        name = "MEM / "; x = 22;
        while (*name) cell(x++, 2, *name++);
        cell(x++, 2, digits[(memory_count / 10) % 10]);
        cell(x, 2, digits[memory_count % 10]);
    }
    for (x = 0; x < 40; ++x) cell(x, 3, ' ');
    x = 0;
    name = "  ZIEL / ";
    while (*name) cell(x++, 3, *name++);
    name = link_host;
    while (*name && x < 35) cell(x++, 3, *name++);
    name = ":6464";
    while (*name && x < 40) cell(x++, 3, *name++);
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

static void cursor_hide(void)
{
    if (cursor_on) {
        cell(col, row, ' ');
        cursor_on = 0;
    }
}

static void scroll(void)
{
    unsigned int i;
    for (i = 200; i < 880; ++i) {
        SCREEN[i] = SCREEN[i + 40];
        COLORS[i] = COLORS[i + 40];
        if ((i & 7) == 0) link_poll();
    }
    for (i = 880; i < 920; ++i) {
        SCREEN[i] = 32;
        COLORS[i] = palettes[palette];
    }
}

static void newline(void)
{
    col = 0;
    if (row == 22) scroll(); else ++row;
}

static void put_char(unsigned char c)
{
    if (c == '\n') { newline(); return; }
    if (col >= 40) newline();
    cell(col++, row, c);
    link_poll();
}

void ui_text(const char *text)
{
    unsigned char length;
    cursor_hide();
    while (*text) {
        if (*text == '\n') { newline(); ++text; continue; }
        if (*text == ' ') { put_char(' '); ++text; continue; }
        length = 0;
        while (text[length] && text[length] != ' ' && text[length] != '\n' && length < 40) ++length;
        if (length <= 40 && col && col + length > 40) newline();
        while (length--) put_char(*text++);
    }
}

void ui_line(const char *text)
{
    ui_text(text);
    newline();
}

void ui_system(const char *text)
{
    if (col) newline();
    ui_text("SYS > ");
    ui_line(text);
}

void ui_gizmo(const char *text)
{
    if (col) newline();
    if (gizmo_first) ui_text("GZM > ");
    else ui_text("      ");
    ui_line(text);
    gizmo_first = 0;
}

void ui_gizmo_start(void) { gizmo_first = 1; }

void ui_prompt(const char *input)
{
    cursor_hide();
    if (col) newline();
    editor_length = (unsigned char)strlen(input);
    ui_text("USR > ");
    ui_text(input);
}

void ui_input_char(unsigned char c)
{
    cursor_hide();
    put_char(c);
    ++editor_length;
}

void ui_input_backspace(void)
{
    cursor_hide();
    if (!editor_length) return;
    --editor_length;
    if (col) --col;
    else if (row > 5) { --row; col = 39; }
    cell(col, row, ' ');
}

void ui_waiting(unsigned char value) { waiting = value; }
void ui_memory_count(unsigned char count)
{
    memory_count = count;
    shown_state = 255;
}

void ui_clear(void)
{
    unsigned int i;
    for (i = 200; i < 920; ++i) {
        SCREEN[i] = 32;
        COLORS[i] = palettes[palette];
        if ((i & 7) == 0) link_poll();
    }
    row = 5; col = 0; cursor_on = 0;
}

void ui_theme(void)
{
    unsigned int i;
    palette = (palette + 1) % 3;
    for (i = 0; i < 1000; ++i) {
        COLORS[i] = i < 40 || i >= 960 ? accents[palette] :
            (i < 80 || (i >= 160 && i < 200) ||
             (i >= 920 && i < 960) ? 11 : palettes[palette]);
        if ((i & 7) == 0) link_poll();
    }
    REGISTER(0xd027) = accents[palette];
    REGISTER(0xd028) = accents[palette];
}

void ui_status_changed(void)
{
    shown_state = 255;
}

void ui_key_sound(void)
{
    REGISTER(0xd400) = 90;
    REGISTER(0xd401) = 18;
    REGISTER(0xd405) = 0;
    REGISTER(0xd406) = 0x22;
    SID_VOICE = 0x11;
    sound_ticks = 2;
}

void ui_tick(unsigned char active)
{
    unsigned char raster = REGISTER(0xd012);
    unsigned char frame;
    if (raster >= previous_raster) { previous_raster = raster; return; }
    previous_raster = raster;
    if (sound_ticks && !--sound_ticks) SID_VOICE = 0x10;
    cell(37, 24, waiting ? '.' : ' ');
    cell(38, 24, waiting && (pulse & 1) ? '.' : ' ');
    if (++pulse >= (active ? 5 : 16)) {
        pulse = 0;
        phase = (phase + 1) & 3;
        frame = active ? phase : (phase == 3 ? 1 : phase);
        REGISTER(0x67f8) = 0xe0 + frame * 2;
        REGISTER(0x67f9) = 0xe1 + frame * 2;
    }
    if (shown_state != link_state) { shown_state = link_state; header_status(); }
    cursor_hide();
    if (!waiting && (phase & 1)) {
        if (col >= 40) newline();
        cell(col, row, ' ');
        SCREEN[(unsigned int)row * 40 + col] = 96;
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
    row = 0;
    ui_line("  GIZMO-64   /   TERMINAL 0.2.2");
    ui_line("  SYSTEMKERN  //  C64 ULTIMATE");
    ui_line("  LINK / INITIALISIERT");
    ui_line("  ZIEL / 192.168.178.244:6464");
    ui_line(" --------------------------------------");
    for (i = 1; i < 39; ++i) SCREEN[160 + i] = 95;
    for (i = 2; i < 10; ++i) SCREEN[i] |= 0x80;
    row = 5; col = 0;
    make_sprites();
    REGISTER(0xd015) = 3;
    REGISTER(0xd010) = 3;
    REGISTER(0xd000) = 280 - 256;
    REGISTER(0xd001) = 50;
    REGISTER(0xd002) = 304 - 256;
    REGISTER(0xd003) = 50;
    REGISTER(0xd01b) &= 0xfc;
    REGISTER(0xd01c) &= 0xfc;
    REGISTER(0xd01d) &= 0xfc;
    REGISTER(0xd017) &= 0xfc;
    REGISTER(0xd027) = accents[palette];
    REGISTER(0xd028) = accents[palette];
    REGISTER(0x67f8) = 0xe0;
    REGISTER(0x67f9) = 0xe1;
    for (i = 920; i < 1000; ++i) { SCREEN[i] = 32; COLORS[i] = 11; }
    row = 23;
    ui_line(" --------------------------------------");
    for (i = 1; i < 39; ++i) SCREEN[920 + i] = 95;
    ui_text(" F1 FARBE  HELP BEFEHLE  GIZMO 0.2.2");
    row = 5; col = 0;
    REGISTER(0xd418) = 15;
}

#ifdef GIZMO_TEST
unsigned char ui_test_cell(unsigned char x, unsigned char y)
{
    return SCREEN[(unsigned int)y * 40 + x];
}
unsigned char ui_test_sprite(unsigned char frame, unsigned char offset)
{
    return SPRITES[(unsigned int)frame * 128 + offset];
}
unsigned char ui_test_register(unsigned int address)
{
    return REGISTER(address);
}
void ui_test_set_register(unsigned int address, unsigned char value)
{
    REGISTER(address) = value;
}
#endif
