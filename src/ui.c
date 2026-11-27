#include <string.h>
#include <cbm.h>
#include "ui.h"
#include "ui_bitmap.h"
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
#define SCREEN ((volatile unsigned char *)0x8400)
#define COLORS ((volatile unsigned char *)0xd800)
#define BORDER (*(volatile unsigned char *)0xd020)
#define BACKGROUND (*(volatile unsigned char *)0xd021)
#define SPRITES ((volatile unsigned char *)0x8800)
#define SID_VOICE (*(volatile unsigned char *)0xd404)
#define REGISTER(a) (*(volatile unsigned char *)(a))
extern const unsigned char gizmo_font[2048];
extern const unsigned char display_assets[3776];
extern void border_irq_install(void);
extern unsigned char border_sprites_enabled;
extern unsigned char *bitmap_src,*bitmap_dst;
extern unsigned char bitmap_copy_pages,bitmap_copy_remainder;
extern void bitmap_copy_rows(void);
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
static unsigned char menu,menu_choice,keymap,mode,safe_logo;
static unsigned char prefs[8],prefs_result;
static unsigned char rendered_input[74],rendered_count;

static unsigned char prefs_valid(void)
{
    unsigned char i,check=0;
    for (i=0;i<7;++i) check^=prefs[i];
    return prefs[0]=='G' && prefs[1]=='Z' && prefs[2]=='P' &&
           prefs[3]==1 && prefs[4]<2 && prefs[5]<3 && prefs[6]<2 &&
           prefs[7]==check;
}

static void prefs_load(void)
{
    if (cbm_load("GIZMOPRF",8,prefs)==8 && prefs_valid()) {
        palette=prefs[4];mode=prefs[5];keymap=prefs[6];
    }
}

static void prefs_save(void)
{
    unsigned char i,check=0;
    if (link_waiting) {prefs_result=3;return;}
    prefs[0]='G';prefs[1]='Z';prefs[2]='P';prefs[3]=1;
    prefs[4]=palette;prefs[5]=mode;prefs[6]=keymap;
    for (i=0;i<7;++i) check^=prefs[i];
    prefs[7]=check;
    prefs_result=cbm_save("@0:GIZMOPRF",8,prefs,8) ? 2 : 1;
}

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
            raw_cell(x, y, safe_logo && !menu ? gizmo_header[(unsigned int)y * 40 + x] : 32,
                     accents[palette]);
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
    else if (link_state == LINK_OFFLINE || link_state == LINK_ERROR)
        print_at(0, 3, "SYSTEM UNAVAILABLE", accents[palette]);
    else if (link_state != LINK_ONLINE)
        print_at(0, 3, "INITIALIZING", accents[palette]);
}

static void draw_footer(void)
{
    clear_row(21, accents[palette]);
    print_at(0, 21, "----------------------------------------", accents[palette]);
    clear_row(24, accents[palette]);
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

static void draw_line(unsigned char row,unsigned char index)
{
    unsigned char x;
    for (x=0;x<40;++x) {
        raw_cell(x,DIALOG_TOP+row,history[index][x],palettes[palette]);
        if ((x&7)==0) link_poll();
    }
}

static void draw_menu(void)
{
    unsigned char y,x,selected=menu_choice+6;
    for (y=4;y<=20;++y) clear_row(y,palettes[palette]);
    print_at(1,4,"GIZMO // OPTIONS",accents[palette]);
    print_at(1,6,"COLOR",palettes[palette]);
    print_at(18,6,palette ? "ICE BLUE" : "GREEN",palettes[palette]);
    print_at(1,7,"TEXT SIZE",palettes[palette]);
    print_at(18,7,mode==0 ? "STANDARD" : mode==1 ? "COMPACT" : "DENSE",palettes[palette]);
    print_at(1,8,"KEYBOARD",palettes[palette]);
    print_at(18,8,keymap ? "QWERTZ" : "QWERTY",palettes[palette]);
    print_at(1,9,"LOGO",palettes[palette]);
    print_at(18,9,safe_logo ? "SAFE" : "BORDER",palettes[palette]);
    print_at(1,10,"SOUND",palettes[palette]);
    print_at(18,10,sound_enabled ? "ON" : "OFF",palettes[palette]);
    print_at(1,11,"SAVE SETTINGS TO DRIVE 8",palettes[palette]);
    for (x=0;x<40;++x) SCREEN[(unsigned int)selected*40+x]^=0x80;
    print_at(0,13,"CURSOR UP/DOWN // RETURN TO CHANGE",palettes[palette]);
    print_at(0,15,"F3/F5 SCROLLBACK  F7 LIVE  F8 SERVICE",palettes[palette]);
    print_at(0,16,"COMMODORE KEY / HELP CLOSE",palettes[palette]);
    if (prefs_result==1) print_at(0,18,"SETTINGS SAVED ON DRIVE 8",palettes[palette]);
    else if (prefs_result==2) print_at(0,18,"SAVE FAILED // CHECK DRIVE 8",palettes[palette]);
    else if (prefs_result==3) print_at(0,18,"SAVE LATER // GIZMO IS ANSWERING",palettes[palette]);
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
    if (menu) draw_menu();
    else if (service) draw_service();
    else draw_dialog();
    draw_footer();
}

static void commit(void)
{
    unsigned char x, index;
    unsigned char was_full=history_count>=DIALOG_ROWS;
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
    if (service || menu || !live) return;
    if (was_full) {
        bitmap_src=(unsigned char *)(SCREEN+(DIALOG_TOP+1)*40);
        bitmap_dst=(unsigned char *)(SCREEN+DIALOG_TOP*40);
        bitmap_copy_pages=2;
        bitmap_copy_remainder=128;
        bitmap_copy_rows();
        link_poll();
    }
    draw_line(was_full ? DIALOG_ROWS-1 : history_count-1,index);
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
    if (!menu) draw_dialog();
}

void ui_scroll_next(void)
{
    unsigned char end;
    if (service || live) return;
    end = history_count > DIALOG_ROWS ? history_count - DIALOG_ROWS : 0;
    if (view_start + 9 >= end) { live = 1; view_start = end; }
    else view_start += 9;
    if (!menu) draw_dialog();
}

void ui_scroll_live(void)
{
    if (service) return;
    live = 1;
    view_start = history_count > DIALOG_ROWS ? history_count - DIALOG_ROWS : 0;
    if (!menu) draw_dialog();
}

unsigned char ui_service_toggle(void)
{
    unsigned char was_menu=menu;
    service = !service;
    menu=0;
    if (was_menu) {
        unsigned int i;
        for (i=0;i<1024;++i) {
            ((volatile unsigned char *)0xa400)[i]=gizmo_font[1024+i];
            if ((i&31)==0) link_poll();
        }
    }
    redraw();
    return service;
}

unsigned char ui_service_active(void) { return service; }
void ui_waiting(unsigned char value) { waiting = value; }
void ui_memory_count(unsigned char count) { memory_count = count; if (service) draw_service(); }
void ui_status_changed(void) { last_state = 255; }

void ui_theme(void)
{
    unsigned char s;
    palette ^= 1;
    for (s=0;s<8;++s) REGISTER(0xd027+s)=accents[palette];
    redraw();
    clear_row(22,palettes[palette]);clear_row(23,palettes[palette]);
    print_at(0,22,"YOU: ",accents[palette]);
    rendered_count=0;cursor_on=0;
    ui_prompt(editor_text);
}

unsigned char ui_menu_active(void) {return menu;}
unsigned char ui_keyboard_layout(void) {return keymap;}
unsigned char ui_keyboard_map(unsigned char c)
{
    if (!keymap) return c;
    if (c=='Y') return 'Z';if (c=='Z') return 'Y';
    if (c=='y') return 'z';if (c=='z') return 'y';
    if (c==0xd9) return 0xda;if (c==0xda) return 0xd9;
    return c;
}
void ui_help_toggle(void)
{
    unsigned int i;
    menu=!menu;service=0;
    for (i=0;i<1024;++i) {
        ((volatile unsigned char *)0xa400)[i]=menu ?
            (unsigned char)~display_assets[(unsigned int)mode*1024+i] :
            gizmo_font[1024+i];
        if ((i&31)==0) link_poll();
    }
    redraw();
}
void ui_menu_move(signed char direction)
{
    if (!menu) return;
    if (direction<0) menu_choice=menu_choice ? menu_choice-1 : 5;
    else menu_choice=menu_choice==5 ? 0 : menu_choice+1;
    draw_menu();
}
void ui_border_toggle(void)
{
    if (!REGISTER(0x02a6)) return;
    safe_logo=!safe_logo;
    border_sprites_enabled=safe_logo ? 0 : 0xff;
    REGISTER(0xd015)=border_sprites_enabled;
    redraw();
}
static void font_mode(unsigned char next)
{
    unsigned int i;
    if (mode==next) return;
    mode=next;
    for (i=0;i<1024;++i) {
        ((volatile unsigned char *)0xa000)[i]=display_assets[(unsigned int)mode*1024+i];
        if (menu) ((volatile unsigned char *)0xa400)[i]=
            (unsigned char)~display_assets[(unsigned int)mode*1024+i];
        if ((i&31)==0) link_poll();
    }
    if (menu) draw_menu();
}
void ui_smaller(void) {if (mode<2) font_mode(mode+1);}
void ui_larger(void) {if (mode) font_mode(mode-1);}
void ui_menu_activate(void)
{
    if (!menu) return;
    switch (menu_choice) {
        case 0: ui_theme();break;
        case 1: font_mode(mode==2 ? 0 : mode+1);break;
        case 2: keymap^=1;draw_menu();break;
        case 3: ui_border_toggle();break;
        case 4: ui_sound_toggle();draw_menu();break;
        case 5: prefs_save();draw_menu();break;
    }
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
    unsigned int i;
    for (i=0;i<704;++i) {
        SPRITES[i]=display_assets[3072+i];
        if ((i&63)==0) link_poll();
    }
}

void ui_prompt(const char *input)
{
    unsigned char i, x, y, length, start,count,old_count=rendered_count;
    editor_text = input;
    length = (unsigned char)strlen(input);
    start = length > 74 ? length - 74 : 0;
    count=length-start;
    if (cursor_on) raw_cell(cursor_x,cursor_y,32,palettes[palette]);
    for (i=0;i<count || i<old_count;++i) {
        unsigned char next=i<count ? input[start+i] : 0;
        if (i>=old_count || i>=count || rendered_input[i]!=next) {
            x=i+5;y=x<40 ? 22 : 23;
            if (x>=40) x-=40;
            cell(x,y,next ? next : 32,palettes[palette]);
        }
        if (i<count) rendered_input[i]=next;
    }
    rendered_count=count;
    x=count+5;cursor_y=x<40 ? 22 : 23;
    cursor_x=x<40 ? x : x-40;
    if (cursor_on) raw_cell(cursor_x,cursor_y,96,accents[palette]);
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
        REGISTER(0x87ff) = 0x27 + phase;
        if (cursor_on) {
            raw_cell(cursor_x,cursor_y,32,palettes[palette]);
            cursor_on=0;
        } else if (!waiting || editor_text[0]) {
            raw_cell(cursor_x,cursor_y,96,accents[palette]);
            cursor_on=1;
        }
    }
    if (last_state != link_state) {
        last_state = link_state;
        if (service) draw_service();
        else draw_status();
    }
}

void ui_init(void)
{
    unsigned int i,x;unsigned char s;
    prefs_load();
    safe_logo=REGISTER(0x02a6) ? 0 : 1;
    REGISTER(0xdd02) |= 3;
    REGISTER(0xdd00) = (REGISTER(0xdd00) & 0xfc) | 1;
    REGISTER(0xd011) = (REGISTER(0xd011) & 0x9f) | 0x10;
    REGISTER(0xd016) = (REGISTER(0xd016) & 0xef) | 8;
    BORDER = BACKGROUND = 0;
    REGISTER(0xd018) = 0x18; /* $8400 screen, $a000 RAM font, sprites at the proven $8800. */
#ifndef GIZMO_TEST
    for (i = 0; i < 2048; ++i) {
        ((volatile unsigned char *)0xa000)[i] = i<1024 ?
            display_assets[(unsigned int)mode*1024+i] : gizmo_font[i];
        if ((i & 7) == 0) link_poll();
    }
#endif
    for (i = 0; i < 1000; ++i) { SCREEN[i] = 32; COLORS[i] = palettes[palette]; }
    make_sprites();
    for (s=0;s<8;++s) {
        x=24+(unsigned int)(s==7 ? 240 : s*48);
        REGISTER(0xd000+s*2)=(unsigned char)x;
        REGISTER(0xd001+s*2)=20;
        SCREEN[1016+s]=0x20+(s==7 ? 7 : s);
        REGISTER(0xd027+s)=accents[palette];
    }
    REGISTER(0xd010)=0xe0;
    REGISTER(0xd015)=safe_logo ? 0 : 0xff;
    border_sprites_enabled=safe_logo ? 0 : 0xff;
    REGISTER(0xd01b)=0;REGISTER(0xd01c)=0;
    REGISTER(0xd01d)=0xff;REGISTER(0xd017)=0;
    REGISTER(0xd418) = 15;
    REGISTER(0xbfff)=0; /* VIC idle fetch in bank 2 must not expose random bytes in the open border. */
    if (!safe_logo) border_irq_install();
    redraw();
    clear_row(22,palettes[palette]);clear_row(23,palettes[palette]);
    print_at(0,22,"YOU: ",accents[palette]);
    ui_prompt("");
}

#ifdef GIZMO_DEMO
void ui_demo_seed(void)
{
    unsigned char i;
    static const char *const lines[]={
        "YOU: GOOD EVENING, GIZMO.",
        "GZM: GOOD EVENING. HOW WAS YOUR DAY?",
        "YOU: WE VISITED THE OLD OBSERVATORY.",
        "GZM: THE HILL ABOVE THE HARBOR?",
        "YOU: YES. THE SKY WAS CLEAR AT DUSK.",
        "GZM: THAT SOUNDS LIKE A FINE VIEW."
    };
    for (i=0;i<sizeof(lines)/sizeof(lines[0]);++i) ui_line(lines[i]);
}
#endif

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
