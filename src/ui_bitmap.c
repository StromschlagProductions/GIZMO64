/* Experimental VIC-II bitmap presentation. Transport remains in src/link.c. */
#include <string.h>
#include "ui.h"
#include "ui_bitmap.h"
#include "link.h"
#include "header_art.h"

#define HISTORY_LINES 112
#define BITMAP ((volatile unsigned char *)0xa000)
#define SCREEN ((volatile unsigned char *)0x8400)
#define SPRITES ((volatile unsigned char *)0x8800)
#define REG(a) (*(volatile unsigned char *)(a))
extern const unsigned char gizmo_font[2048];
extern const unsigned char display_assets[3776];
extern void border_irq_install(void);
extern unsigned char border_sprites_enabled;

static const unsigned char foreground[2]={5,3};
static const unsigned char accent[2]={13,14};
static const unsigned char heights[3]={8,7,6};
static const unsigned char ink_rows[3]={7,6,5};
static const unsigned int bitmap_rows[25]={
    0,320,640,960,1280,1600,1920,2240,2560,2880,
    3200,3520,3840,4160,4480,4800,5120,5440,5760,6080,
    6400,6720,7040,7360,7680
};
static unsigned char history[HISTORY_LINES][40];
static unsigned char history_start,history_count,view_start,live=1;
static unsigned char draft[40],draft_col,gizmo_first=1;
static unsigned char service_lines[8][40],service_start,service_count;
static unsigned char palette,mode,menu,service,safe_logo,batch_render;
static unsigned char waiting,sound_enabled,sound_ticks,memory_count=255;
static unsigned char cursor_on=1,pulse,phase,previous_raster=255,last_state=255;
static const char *editor_text="";

static unsigned char code(unsigned char c)
{
    if (c>=0xc1 && c<=0xda) return c-0xc0;
    if (c>=0x61 && c<=0x7a) c-=32;
    if (c>=0x41 && c<=0x5a) return c-64;
    if (c>=32 && c<=95) return c;
    return 63;
}

static volatile unsigned char *pixel_byte(unsigned char x,unsigned char y)
{
    return BITMAP+bitmap_rows[y>>3]+((unsigned int)x<<3)+(y&7);
}

static void glyph(unsigned char x,unsigned char y,unsigned char c)
{
    unsigned char row;
    const unsigned char *source=display_assets+(unsigned int)mode*1024+(unsigned int)c*8;
    if (x>=40) return;
    for (row=0;row<ink_rows[mode];++row)
        if ((unsigned int)y+row<200) *pixel_byte(x,y+row)=source[row];
    link_poll();
}

static void text(unsigned char x,unsigned char y,const char *s)
{
    while (*s && x<40) glyph(x++,y,code(*s++));
}

static void clear_bitmap(void)
{
    unsigned int i;
    for (i=0;i<8000;i+=256) {
        memset((void *)(BITMAP+i),0,256);
        link_poll();
    }
}

static unsigned char top(void) { return safe_logo ? 24 : 0; }
static unsigned char input_y(void) { return 200-(heights[mode]<<1); }
unsigned char ui_visible_rows(void)
{
    return (input_y()-top()-2)/heights[mode];
}
unsigned char ui_mode(void) { return mode; }

static unsigned char slot(unsigned char logical)
{
    unsigned char index=history_start+logical;
    if (index>=HISTORY_LINES) index-=HISTORY_LINES;
    return index;
}

static void line_at(unsigned char row,const unsigned char *line)
{
    unsigned char x,y=top()+row*heights[mode];
    for (x=0;x<40;++x) if (line[x]!=32) glyph(x,y,line[x]);
}

static void draw_safe_logo(void)
{
    unsigned char x,y,code_at;
    if (!safe_logo) return;
    for (y=0;y<24;++y) for (x=0;x<40;++x) {
        code_at=gizmo_header[(unsigned int)(y>>3)*40+x];
        if (code_at!=32)
            *pixel_byte(x,y)=gizmo_font[(unsigned int)code_at*8+(y&7)];
    }
    for (x=0;x<120;++x) SCREEN[x]=(accent[palette]<<4);
}

static void draw_input(void)
{
    unsigned char y,x,length,start,col=5,row=0;
    unsigned char h=heights[mode],base=input_y();
    for (y=base;y<200;++y) {
        for (x=0;x<40;++x) *pixel_byte(x,y)=0;
        if ((y&3)==0) link_poll();
    }
    text(0,base,"YOU: ");
    length=(unsigned char)strlen(editor_text);
    start=length>74 ? length-74 : 0;
    for (x=start;x<length;++x) {
        if (col==40) { col=0;row=1; }
        glyph(col++,base+row*h,code(editor_text[x]));
    }
    if (col==40) { col=0;row=1; }
    if (cursor_on) glyph(col,base+row*h,96);
}

static void draw_status(void)
{
    if (menu || service) return;
    if (!live) text(0,top(),"SCROLLBACK / F7 LIVE");
    else if (link_state==LINK_OFFLINE || link_state==LINK_ERROR)
        text(0,top(),"SYSTEM UNAVAILABLE");
    else if (link_state!=LINK_ONLINE) text(0,top(),"INITIALIZING");
}

static void draw_service(void)
{
    unsigned char i,index,h=heights[mode];
    text(0,0,"SERVICE // F8 CLOSE");
    text(0,h*2,"STATE:");text(8,h*2,link_state_name());
    text(0,h*3,"HOST:");text(7,h*3,link_host);
    text(0,h*4,"ACIA $DE00 / 2400 BAUD / PORT 6464");
    for (i=0;i<service_count;++i) {
        index=service_start+i;if (index>=8) index-=8;
        {
            unsigned char x;
            for (x=0;x<40;++x) if (service_lines[index][x]!=32)
                glyph(x,(i+7)*h,service_lines[index][x]);
        }
    }
}

static void draw_menu(void)
{
    unsigned char h=heights[mode];
    text(0,0,"GIZMO // HELP");
    text(0,h*2,"F1  CHANGE COLOR");
    text(0,h*3,"F2  SMALLER TEXT");
    text(0,h*4,"F3  PREVIOUS PAGE");
    text(0,h*5,"F4  LARGER TEXT");
    text(0,h*6,"F5  NEXT PAGE");
    text(0,h*7,"F6  SAFE LOGO / BORDER LOGO");
    text(0,h*8,"F7  LIVE CONVERSATION");
    text(0,h*9,"F8  TECHNICAL SERVICE");
    text(0,h*10,"COMMODORE+H  CLOSE HELP");
    text(0,h*12,"SERVICE: DIAG HEX IP UPLINK OFFLINE");
    text(0,h*13,"SERVICE: PING STATUS CLS SOUND");
    text(0,h*15,"SOUND IS OFF UNTIL ENABLED IN SERVICE");
}

static void redraw(void)
{
    unsigned char y,logical,rows=ui_visible_rows();
    clear_bitmap();
    draw_safe_logo();
    if (menu) draw_menu();
    else if (service) draw_service();
    else {
        for (y=0;y<rows;++y) {
            logical=view_start+y;
            if (logical>=history_count) break;
            line_at(y,history[slot(logical)]);
        }
        draw_status();
    }
    y=input_y()-2;
    if (!menu && !service) {
        unsigned char x;
        for (x=0;x<40;++x) *pixel_byte(x,y)=0xaa;
    }
    draw_input();
}

static void commit(void)
{
    unsigned char x,index,rows=ui_visible_rows();
    if (history_count==HISTORY_LINES) {
        if (!live && view_start) --view_start;
        ++history_start;if (history_start==HISTORY_LINES) history_start=0;
        index=slot(HISTORY_LINES-1);
    } else {index=slot(history_count);++history_count;}
    for (x=0;x<40;++x) history[index][x]=x<draft_col ? draft[x] : 32;
    draft_col=0;
    if (live) view_start=history_count>rows ? history_count-rows : 0;
    if (!menu && !service && !batch_render) redraw();
}

static void put_char(unsigned char c)
{
    if (c=='\n') {commit();return;}
    if (draft_col==40) commit();
    draft[draft_col++]=code(c);
    link_poll();
}

void ui_text(const char *s)
{
    unsigned char length;
    while (*s) {
        if (*s=='\n') {commit();++s;continue;}
        if (*s==' ') {put_char(' ');++s;continue;}
        length=0;
        while (s[length] && s[length]!=' ' && s[length]!='\n' && length<40) ++length;
        if (draft_col && draft_col+length>40) commit();
        while (length--) put_char(*s++);
    }
}
void ui_line(const char *s) {ui_text(s);commit();}
void ui_submit(const char *s) {ui_text("YOU: ");ui_line(s);}
void ui_gizmo(const char *s)
{
    ui_text(gizmo_first ? "GZM: " : "     ");ui_line(s);gizmo_first=0;
}
void ui_gizmo_start(void) {gizmo_first=1;}

void ui_system(const char *s)
{
    unsigned char x,index,length;
    if (!service) {
        if (link_state==LINK_ONLINE && (strstr(s,"TIMEOUT") || strstr(s,"FEHL") ||
            strstr(s,"OVERRUN") || strstr(s,"ABBRUCH"))) ui_line("SYSTEM UNAVAILABLE");
        return;
    }
    if (service_count==8) {
        ++service_start;if (service_start==8) service_start=0;
        index=service_start+7;if (index>=8) index-=8;
    } else {index=service_start+service_count;if (index>=8) index-=8;++service_count;}
    length=(unsigned char)strlen(s);
    for (x=0;x<40;++x) service_lines[index][x]=x<length ? code(s[x]) : 32;
    redraw();
}

void ui_clear(void)
{
    history_start=history_count=view_start=draft_col=0;live=1;gizmo_first=1;redraw();
}
void ui_scroll_back(void)
{
    unsigned char rows=ui_visible_rows(),step=rows>3 ? rows-3 : 1;
    if (service || history_count<=rows) return;
    if (live) {live=0;view_start=history_count-rows;}
    view_start=view_start>step ? view_start-step : 0;
    if (!menu) redraw();
}
void ui_scroll_next(void)
{
    unsigned char rows=ui_visible_rows(),step=rows>3 ? rows-3 : 1;
    unsigned char end=history_count>rows ? history_count-rows : 0;
    if (service || live) return;
    if (view_start+step>=end) {live=1;view_start=end;} else view_start+=step;
    if (!menu) redraw();
}
void ui_scroll_live(void)
{
    if (service) return;
    live=1;view_start=history_count>ui_visible_rows() ? history_count-ui_visible_rows() : 0;
    if (!menu) redraw();
}
unsigned char ui_service_toggle(void) {service=!service;menu=0;redraw();return service;}
unsigned char ui_service_active(void) {return service;}
void ui_help_toggle(void) {menu=!menu;service=0;redraw();}
void ui_border_toggle(void)
{
    if (!REG(0x02a6)) return; /* NTSC: keep the reliable in-screen logo. */
    safe_logo=!safe_logo;REG(0xd015)=safe_logo ? 0 : 0xff;
    border_sprites_enabled=safe_logo ? 0 : 0xff;
    if (live) view_start=history_count>ui_visible_rows() ? history_count-ui_visible_rows() : 0;
    redraw();
}
static void resize(unsigned char smaller)
{
    if (smaller) {if (mode==2) return;++mode;}
    else {if (mode==0) return;--mode;}
    if (live) view_start=history_count>ui_visible_rows() ? history_count-ui_visible_rows() : 0;
    else if (view_start+ui_visible_rows()>history_count)
        view_start=history_count>ui_visible_rows() ? history_count-ui_visible_rows() : 0;
    redraw();
}
void ui_smaller(void) {resize(1);}
void ui_larger(void) {resize(0);}
void ui_theme(void)
{
    unsigned int i;unsigned char s;
    palette^=1;
    for (i=0;i<1000;++i) SCREEN[i]=foreground[palette]<<4;
    for (s=0;s<8;++s) REG(0xd027+s)=accent[palette];
    redraw();
}
void ui_sound_toggle(void) {sound_enabled=!sound_enabled;}
void ui_key_sound(void)
{
    if (!sound_enabled) return;
    REG(0xd400)=90;REG(0xd401)=18;REG(0xd405)=0;REG(0xd406)=0x22;
    REG(0xd404)=0x11;sound_ticks=2;
}
void ui_waiting(unsigned char value) {waiting=value;}
void ui_memory_count(unsigned char value) {memory_count=value;if (service) redraw();}
void ui_status_changed(void) {last_state=255;}
void ui_prompt(const char *s) {editor_text=s;draw_input();}
void ui_input_char(unsigned char c) {(void)c;draw_input();}
void ui_input_backspace(void) {draw_input();}

void ui_tick(unsigned char active)
{
    unsigned char raster=REG(0xd012);
    if (raster>=previous_raster) {previous_raster=raster;return;}
    previous_raster=raster;
    if (sound_ticks && !--sound_ticks) REG(0xd404)=0x10;
    if (++pulse>=8) {
        pulse=0;
        phase=active ? (phase+1)&3 : 0;
        SCREEN[1023]=0x27+phase;
        cursor_on=!cursor_on;
        draw_input();
    }
    if (last_state!=link_state) {last_state=link_state;if (!menu && !service) redraw();}
    (void)waiting;
}

void ui_init(void)
{
    unsigned int i;unsigned char s;unsigned int x;
    safe_logo=REG(0x02a6) ? 0 : 1; /* PAL border; NTSC safe in-screen logo. */
    REG(0xdd02)|=3;
    REG(0xdd00)=(REG(0xdd00)&0xfc)|1; /* VIC bank 2: $8000-$bfff. */
    REG(0xd011)=(REG(0xd011)&0x87)|0x38; /* 25 rows, bitmap, display on. */
    REG(0xd016)=(REG(0xd016)&0xef)|8;
    REG(0xd020)=REG(0xd021)=0;
    REG(0xd018)=0x18; /* $8400 screen, $a000 bitmap. */
    for (i=0;i<1000;++i) SCREEN[i]=foreground[palette]<<4;
    for (i=0;i<704;++i) {SPRITES[i]=display_assets[3072+i];if ((i&63)==0) link_poll();}
    for (s=0;s<8;++s) {
        x=24+(unsigned int)(s==7 ? 240 : s*48);
        REG(0xd000+s*2)=(unsigned char)x;
        REG(0xd001+s*2)=20;
        SCREEN[1016+s]=0x20+(s==7 ? 7 : s);
        REG(0xd027+s)=accent[palette];
    }
    REG(0xd010)=0xe0; /* Sprites 5, 6 and wave sprite 7 have X high bit. */
    REG(0xd015)=safe_logo ? 0 : 0xff;
    border_sprites_enabled=safe_logo ? 0 : 0xff;
    REG(0xd01b)=0;REG(0xd01c)=0;REG(0xd01d)=0xff;REG(0xd017)=0;
    REG(0xd418)=15;
    REG(0xbfff)=0; /* Idle graphics byte in VIC bank 2. */
    if (!safe_logo) border_irq_install();
    redraw();
}

#ifdef GIZMO_DEMO
void ui_demo_seed(void)
{
    static const char *const lines[]={
        "YOU: GOOD EVENING, GIZMO.",
        "GZM: GOOD EVENING. HOW WAS YOUR DAY?",
        "YOU: WE VISITED THE OLD OBSERVATORY.",
        "GZM: THE HILL ABOVE THE HARBOR?",
        "YOU: YES. THE SKY WAS CLEAR AT DUSK.",
        "GZM: THAT SOUNDS LIKE A FINE VIEW.",
        "YOU: WE SAW JUPITER THROUGH THE LENS.",
        "GZM: ITS BRIGHT MOONS ARE HARD TO MISS.",
        "YOU: MY FRIEND ADA BROUGHT HER CAMERA.",
        "GZM: DID SHE CATCH THE CITY LIGHTS?",
        "YOU: SHE DID, JUST AFTER SUNSET.",
        "GZM: I CAN PICTURE THE BLUE HORIZON.",
        "YOU: THEN WE WALKED DOWN TO THE PIER.",
        "GZM: WAS THE WATER CALM?",
        "YOU: THERE WAS A LITTLE WIND.",
        "GZM: THE HARBOR MUST HAVE FELT ALIVE.",
        "YOU: WE TALKED ABOUT OLD RADIO SETS.",
        "GZM: THE ONES WITH WARM DIAL LIGHTS?",
        "YOU: EXACTLY. ADA REPAIRS THEM.",
        "GZM: THAT TAKES PATIENCE AND CARE.",
        "YOU: SHE FOUND A SET FROM THE 1950S.",
        "GZM: DOES IT STILL PLAY?",
        "YOU: YES, AFTER A NEW CAPACITOR.",
        "GZM: A SMALL FIX CAN SAVE A VOICE.",
        "YOU: TOMORROW WE MAY VISIT THE MUSEUM.",
        "GZM: THE MARITIME EXHIBIT?",
        "YOU: YES. I WANT TO SEE THE MAP ROOM.",
        "GZM: THOSE MAPS HOLD MANY JOURNEYS.",
        "YOU: I ALSO LIKE THE SHIP MODELS.",
        "GZM: THE TINY DETAILS TELL STORIES.",
        "YOU: WE WILL TAKE THE EARLY TRAIN.",
        "GZM: THEN THE MORNING IS YOURS.",
        "YOU: REMIND ME TO BRING THE CAMERA.",
        "GZM: I HEAR YOU. BRING THE CAMERA.",
        "YOU: THANKS. LET US KEEP TALKING.",
        "GZM: OF COURSE. I AM HERE."
    };
    unsigned char i;
    batch_render=1;
    for (i=0;i<sizeof(lines)/sizeof(lines[0]);++i) ui_line(lines[i]);
    batch_render=0;
    redraw();
    last_state=link_state;
}
#endif
