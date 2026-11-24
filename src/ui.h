#ifndef GIZMO_UI_H
#define GIZMO_UI_H
void ui_init(void);
void ui_tick(unsigned char active);
void ui_text(const char *text);
void ui_line(const char *text);
void ui_prompt(const char *input);
void ui_input_char(unsigned char c);
void ui_input_backspace(void);
void ui_clear(void);
void ui_theme(void);
void ui_key_sound(void);
#endif
