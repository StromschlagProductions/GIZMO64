; Read the C= key directly: CIA1 column 7, row 5 (active low).
; Save the column latch and IRQ state so KERNAL scanning is undisturbed.
.export _commodore_pressed
.setcpu "6502"
.segment "CODE"
_commodore_pressed:
    php
    sei
    lda $dc00
    pha
    lda #$7f
    sta $dc00
    lda $dc01
    and #$20
    beq pressed
    ldx #0
    jmp restore
pressed:
    ldx #1
restore:
    pla
    sta $dc00
    plp
    txa
    rts
