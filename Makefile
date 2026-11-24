CC65 ?= cl65
CFLAGS = -t c64 -O -I src -Wl -m,build/GIZMO64.map
SOURCES = src/main.c src/ui.c src/link.c

all: GIZMO64.PRG

GIZMO64.PRG: $(SOURCES) src/ui.h src/link.h
	mkdir -p build
	$(CC65) $(CFLAGS) -o $@ $(SOURCES)

clean:
	rm -rf build GIZMO64.PRG

test:
	mkdir -p build
	$(HOSTCC) -DGIZMO_TEST -I src -Wall -Wextra -o build/link_test tests/link_test.c src/link.c
	./build/link_test
	$(HOSTCC) -DGIZMO_TEST -I src -Wall -Wextra -o build/ui_test tests/ui_test.c src/ui.c
	./build/ui_test

HOSTCC ?= cc

.PHONY: all clean test
