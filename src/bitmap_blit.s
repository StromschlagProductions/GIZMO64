; Copy one 5-pixel-wide glyph into the interleaved C64 HiRes bitmap.
; Parameters live in ZP because cc65 calls this frequently from C.
.export _bitmap_blit, _bitmap_src, _bitmap_dst, _bitmap_count, _bitmap_low
.export _bitmap_copy_pages, _bitmap_copy_remainder, _bitmap_copy_rows
.export _bitmap_copy_scanline
.setcpu "6502"
.include "zeropage.inc"

.segment "BSS"
_bitmap_src:   .res 2
_bitmap_dst:   .res 2
_bitmap_count: .res 1
_bitmap_low:   .res 1
_bitmap_copy_pages: .res 1
_bitmap_copy_remainder: .res 1

.segment "CODE"
_bitmap_blit:
    lda _bitmap_src
    sta ptr1
    lda _bitmap_src+1
    sta ptr1+1
    lda _bitmap_dst
    sta ptr2
    lda _bitmap_dst+1
    sta ptr2+1
    ldx _bitmap_count
    ldy #0
loop:
    lda (ptr1),y
    sta (ptr2),y
    inc _bitmap_low
    lda _bitmap_low
    cmp #8
    bne next
    lda #0
    sta _bitmap_low
    clc
    lda ptr2
    adc #$38          ; +312 when an 8-pixel VIC character block ends
    sta ptr2
    lda ptr2+1
    adc #$01
    sta ptr2+1
next:
    iny
    dex
    bne loop
    rts

; Forward contiguous bitmap copy. Source is above destination, so overlap is safe.
_bitmap_copy_rows:
    lda _bitmap_src
    sta ptr1
    lda _bitmap_src+1
    sta ptr1+1
    lda _bitmap_dst
    sta ptr2
    lda _bitmap_dst+1
    sta ptr2+1
    ldx _bitmap_copy_pages
page:
    cpx #0
    beq remainder
    ldy #0
page_byte:
    lda (ptr1),y
    sta (ptr2),y
    iny
    bne page_byte
    inc ptr1+1
    inc ptr2+1
    dex
    bne page
remainder:
    ldx _bitmap_copy_remainder
    beq copied
    ldy #0
last_byte:
    lda (ptr1),y
    sta (ptr2),y
    iny
    dex
    bne last_byte
copied:
    rts

; Copy 40 scanline bytes with the VIC-II's eight-byte cell stride.
_bitmap_copy_scanline:
    lda _bitmap_src
    sta ptr1
    lda _bitmap_src+1
    sta ptr1+1
    lda _bitmap_dst
    sta ptr2
    lda _bitmap_dst+1
    sta ptr2+1
    ldx #40
scan_byte:
    ldy #0
    lda (ptr1),y
    sta (ptr2),y
    clc
    lda ptr1
    adc #8
    sta ptr1
    bcc :+
    inc ptr1+1
:
    clc
    lda ptr2
    adc #8
    sta ptr2
    bcc :+
    inc ptr2+1
:
    dex
    bne scan_byte
    rts
