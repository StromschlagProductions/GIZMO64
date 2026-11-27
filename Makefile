CC65 ?= cl65
CFLAGS = -t c64 -O -I src -Wl -m,build/GIZMO64.map
SOURCES = src/main.c src/ui.c src/link.c src/font.s src/display_assets.s src/border_irq.s src/bitmap_blit.s src/keyboard_matrix.s

all: GIZMO64.PRG verify-prg

GIZMO64.PRG: $(SOURCES) src/ui.h src/ui_bitmap.h src/link.h assets/gizmo-font.bin assets/display-prototype.bin
	mkdir -p build
	$(CC65) $(CFLAGS) -o $@ $(SOURCES)

verify-prg: GIZMO64.PRG
	python3 tests/prg_test.py

clean:
	rm -rf build GIZMO64.PRG

test:
	mkdir -p build
	$(HOSTCC) -DGIZMO_TEST -I src -Wall -Wextra -o build/link_test tests/link_test.c src/link.c
	./build/link_test
	$(HOSTCC) -DGIZMO_TEST -I src -Wall -Wextra -o build/ui_test tests/ui_test.c src/ui_023.c
	./build/ui_test
	$(HOSTCC) -DGIZMO_TEST -DGIZMO_PETSCII_TEST -I src -Wall -Wextra -o build/charset_conversion_test tests/charset_conversion_test.c src/link.c
	./build/charset_conversion_test
	python3 tests/charset_test.py
	python3 -m unittest discover -s tests -p 'test_*.py'

package: all
	python3 tools/package_030.py

package-022: all
	python3 tools/package_022.py

HOSTCC ?= cc

.PHONY: all clean test verify-prg package package-022
