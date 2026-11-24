#include <string.h>
#include "ui.h"
#include "link.h"

#ifdef GIZMO_TEST
static unsigned char test_screen[1000], test_colors[1000], test_sprites[256];
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
#define SCREEN ((volatile unsigned char *)0x0400)
#define COLORS ((volatile unsigned char *)0xd800)
#define BORDER (*(volatile unsigned char *)0xd020)
#define BACKGROUND (*(volatile unsigned char *)0xd021)
#define SPRITES ((volatile unsigned char *)0x3800)
#define SID_VOICE (*(volatile unsigned char *)0xd404)
#define REGISTER(a) (*(volatile unsigned char *)(a))
#endif

static const unsigned char palettes[3] = {5, 3, 7};
static unsigned char palette;
static unsigned char row = 5;
static unsigned char col;
static unsigned char cursor_on;
static unsigned char pulse;
static unsigned char sound_ticks;
static unsigned char previous_raster;
static unsigned char phase;

static unsigned char screen_code(unsigned char c)
{
    if (c >= 'a' && c <= 'z') c -= 32;
    if (c >= 'A' && c <= 'Z') return c - 64;
    if (c >= 32 && c <= 63) return c;
    return 63;
}

static void cell(unsigned char x, unsigned char y, unsigned char c)
{
    unsigned int offset = (unsigned int)y * 40 + x;
    SCREEN[offset] = screen_code(c);
    COLORS[offset] = palettes[palette];
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
    for (i = 200; i < 960; ++i) {
        SCREEN[i] = SCREEN[i + 40];
        COLORS[i] = COLORS[i + 40];
        if ((i & 7) == 0) link_poll();
    }
    for (i = 960; i < 1000; ++i) {
        SCREEN[i] = 32;
        COLORS[i] = palettes[palette];
    }
}

static void newline(void)
{
    col = 0;
    if (row == 24) scroll(); else ++row;
}

static void put_char(unsigned char c)
{
    if (c == '\n') { newline(); return; }
    if (col == 40) newline();
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

void ui_prompt(const char *input)
{
    cursor_hide();
    if (col) newline();
    ui_text("> ");
    ui_text(input);
}

void ui_input_char(unsigned char c)
{
    cursor_hide();
    put_char(c);
}

void ui_input_backspace(void)
{
    cursor_hide();
    if (col > 2) { --col; cell(col, row, ' '); }
}

void ui_clear(void)
{
    unsigned int i;
    for (i = 200; i < 1000; ++i) {
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
        COLORS[i] = palettes[palette];
        if ((i & 7) == 0) link_poll();
    }
    REGISTER(0xd027) = palettes[palette];
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
    unsigned char x, y, frame;
    if (raster >= previous_raster) { previous_raster = raster; return; }
    previous_raster = raster;
    if (sound_ticks && !--sound_ticks) SID_VOICE = 0x10;
    if (++pulse >= (active ? 5 : 16)) {
        pulse = 0;
        phase = (phase + 1) & 3;
        frame = active ? phase : (phase == 3 ? 1 : phase);
        for (y = 0; y < 21; ++y) {
            for (x = 0; x < 3; ++x) {
                SPRITES[(unsigned int)frame * 64 + y * 3 + x] =
                    (y == (unsigned char)(7 + ((x * 8 + frame * 2) & 7))) ? 0xff : 0;
            }
        }
        REGISTER(0x07f8) = 0xe0 + frame;
    }
    cursor_hide();
    if (phase & 1) { cell(col, row, ' '); SCREEN[(unsigned int)row * 40 + col] = 0xa0; cursor_on = 1; }
}

void ui_init(void)
{
    unsigned int i;
    BORDER = BACKGROUND = 0;
    REGISTER(0xd018) = 0x14;
    for (i = 0; i < 1000; ++i) { SCREEN[i] = 32; COLORS[i] = palettes[palette]; }
    row = 0;
    ui_line("CORE: GIZMO // UNIT-64");
    ui_line("MODE: PC-UPLINK");
    ui_line("MEM: --   LINK: ACTIVE");
    ui_line("----------------------------------------");
    row = 5; col = 0;
    REGISTER(0xd015) |= 1;
    REGISTER(0xd010) |= 1;
    REGISTER(0xd000) = 310 - 256;
    REGISTER(0xd001) = 42;
    REGISTER(0xd027) = palettes[palette];
    for (i = 0; i < 256; ++i) SPRITES[i] = 0;
    REGISTER(0x07f8) = 0xe0;
    REGISTER(0xd418) = 15;
}

#ifdef GIZMO_TEST
unsigned char ui_test_cell(unsigned char x, unsigned char y)
{
    return SCREEN[(unsigned int)y * 40 + x];
}
#endif
