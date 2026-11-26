#ifndef GIZMO_UI_H
#define GIZMO_UI_H
void ui_init(void);
void ui_tick(unsigned char active);
void ui_text(const char *text);
void ui_line(const char *text);
void ui_system(const char *text);
void ui_gizmo(const char *text);
void ui_gizmo_start(void);
void ui_submit(const char *text);
void ui_prompt(const char *input);
void ui_input_char(unsigned char c);
void ui_input_backspace(void);
void ui_clear(void);
void ui_theme(void);
void ui_scroll_back(void);
void ui_scroll_next(void);
void ui_scroll_live(void);
unsigned char ui_service_toggle(void);
unsigned char ui_service_active(void);
void ui_sound_toggle(void);
void ui_status_changed(void);
void ui_waiting(unsigned char waiting);
void ui_memory_count(unsigned char count);
void ui_key_sound(void);
#endif
