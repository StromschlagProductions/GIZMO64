#ifndef GIZMO_LINK_H
#define GIZMO_LINK_H
#define LINK_OFFLINE 0
#define LINK_MODEM 1
#define LINK_DIAL 2
#define LINK_HANDSHAKE 3
#define LINK_VERIFY 4
#define LINK_ONLINE 5
#define LINK_ERROR 6
#define LINK_HANGUP 7
extern unsigned char link_state;
extern unsigned char link_overruns;
extern unsigned char link_drops;
extern char link_host[16];
extern unsigned char link_waiting;
void link_init(void);
void link_tick(void);
void link_poll(void);
void link_connect(void);
void link_offline(void);
void link_ping(void);
void link_diagnostics(void);
void link_hex_dump(void);
unsigned char link_send_text(const char *text);
unsigned char link_set_host(const char *host);
const char *link_state_name(void);
#endif
