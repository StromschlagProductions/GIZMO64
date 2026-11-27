; PAL-only top/bottom border opening for the experimental bitmap client.
; Based on the isolated probe; main C loop still polls the unchanged ACIA link.
.export _border_irq_install, _border_sprites_enabled
.setcpu "6502"

.segment "DATA"
_border_sprites_enabled:
    .byte $ff

.segment "CODE"
_border_irq_install:
    sei
    lda #<open_border
    sta $0314
    lda #>open_border
    sta $0315
    lda $d011
    and #%01111111
    ora #%00001000
    sta $d011
    lda #249
    sta $d012
    lda #$01
    sta $d01a
    sta $d019
    cli
    rts

open_border:
    lda $d019
    and #$01
    bne open_raster
    jmp $ea31          ; preserve the ordinary CIA/KERNAL keyboard and clock IRQ
open_raster:
    lda #0
    sta $d015          ; no mirrored logo in the lower PAL border
    lda $d011
    and #%01110111
    sta $d011
    lda #0
    sta $d012
    lda #<restore_border
    sta $0314
    lda #>restore_border
    sta $0315
    lda #$01
    sta $d019
    jmp $ea81          ; quick KERNAL IRQ exit

restore_border:
    lda $d019
    and #$01
    bne restore_raster
    jmp $ea31
restore_raster:
    lda _border_sprites_enabled
    sta $d015          ; show the logo at Y=20 in the upper border
    lda $d011
    and #%01111111
    ora #%00001000
    sta $d011
    lda #249
    sta $d012
    lda #<open_border
    sta $0314
    lda #>open_border
    sta $0315
    lda #$01
    sta $d019
    jmp $ea81          ; quick VIC IRQ exit; CIA provides normal KERNAL service
