; Isolated PAL VIC-II top-border experiment. No GIZMO code or ACIA access.
; Compare with/without the RSEL raster IRQ by defining BORDER_PROBE_NO_IRQ.
.export _main
.setcpu "6502"
SPRITE_Y = 4

.segment "LOADADDR"
    .word $0801

.segment "CODE"
    .word $080b        ; BASIC line pointer
    .word 10
    .byte $9e,"2064",0 ; SYS 2064 = $0810
    .word 0
    .res 3,0
_main:
    sei
    lda #$ff
    ldx #$00
fill_sprite:
    sta $2000,x
    inx
    cpx #63
    bne fill_sprite

    lda #$80            ; $2000 / 64, bank 0, standard $0400 screen.
    sta $07f8
    lda #$01
    sta $d015
    sta $d027          ; white sprite 0
    lda #160
    sta $d000
    lda #SPRITE_Y
    sta $d001          ; entirely above normal 25-row display
    lda #$00
    sta $d010
    sta $d01d
    sta $d020          ; black frame
    sta $3fff          ; no idle-byte pattern in opened border
    sta $d017
    lda #$06
    sta $d021          ; blue background makes opening measurable
    lda #$1b
    sta $d011          ; 25 rows, display enabled

.ifndef BORDER_PROBE_NO_IRQ
    lda #$7f
    sta $dc0d          ; no CIA IRQ while testing the raster sequence
    lda $dc0d
    lda #<irq_bottom
    sta $0314
    lda #>irq_bottom
    sta $0315
    lda #249
    sta $d012
    lda #$01
    sta $d019
    sta $d01a
.endif
    cli
idle:
    jmp idle

.ifndef BORDER_PROBE_NO_IRQ
irq_bottom:
    lda $d011
    and #%01110111     ; 24 rows, keep DEN/YSCROLL, clear raster bit 8
    sta $d011
    lda #<irq_top
    sta $0314
    lda #>irq_top
    sta $0315
    lda #0
    sta $d012
    lda #$01
    sta $d019
    jmp $ea81          ; quick KERNAL IRQ epilogue; full service at restore

irq_top:
    lda $d011
    and #%01111111
    ora #%00001000     ; restore 25 rows for the next frame
    sta $d011
    lda #<irq_bottom
    sta $0314
    lda #>irq_bottom
    sta $0315
    lda #249
    sta $d012
    lda #$01
    sta $d019
    jmp $ea31
.endif
