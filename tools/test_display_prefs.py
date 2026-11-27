"""Verify device-8 settings survive a fresh C64 emulator process."""
from pathlib import Path
import subprocess
from test_border_probe import png_rows

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "build"
VICE = ROOT / ".local-tools/vice/SDL2VICE-3.9-win64/x64sc.exe"
CC65 = ROOT / ".local-tools/cc65/bin/cl65.exe"
DRIVE = BUILD / "prefs-test.d64"
C1541 = ROOT / ".local-tools/vice/SDL2VICE-3.9-win64/c1541.exe"
SOURCES = ["src/display_prefs_test.c", "src/ui_bitmap.c", "src/link.c",
           "src/font.s", "src/display_assets.s", "src/border_irq.s",
           "src/bitmap_blit.s"]


def build(name: str, define: str = "", source: str = "src/display_prefs_test.c") -> Path:
    program = BUILD / f"DISPLAY-PREFS-{name}.PRG"
    command = [str(CC65), "-t", "c64", "-O", "-I", "src"]
    if define:
        command.append(f"-D{define}")
    subprocess.run([*command, "-o", str(program), source, *SOURCES[1:]],
                   cwd=ROOT, check=True)
    return program


def capture(name: str, program: Path) -> Path:
    image = BUILD / f"display-prefs-{name}.png"
    image.unlink(missing_ok=True)
    command = [str(VICE), "-VICIImodel", "6569", "-VICIIborders", "1",
               "-8", str(DRIVE), "-autostartprgmode", "1",
               "-autostart", str(program), "-exitscreenshot", str(image),
               "-limitcycles", "25000000", "-silent"]
    result = subprocess.run(command, cwd=VICE.parent, timeout=120)
    if result.returncode not in (0, 1) or not image.is_file():
        raise RuntimeError(f"VICE did not capture {name}")
    return image


def main() -> None:
    DRIVE.unlink(missing_ok=True)
    subprocess.run([str(C1541), "-format", "GIZMO,01", "d64", str(DRIVE)],
                   cwd=ROOT, check=True, capture_output=True)
    writer = build("WRITE", "GIZMO_PREFS_WRITE")
    reader = build("READ")
    before = capture("default", reader)
    saved = capture("saved", writer)
    listing = subprocess.run([str(C1541), str(DRIVE), "-dir"], cwd=ROOT,
                             check=True, capture_output=True, text=True).stdout
    if "GIZMOPRF" not in listing.upper():
        raise RuntimeError(f"Expected saved settings on D64, got {listing}")
    after = capture("reloaded", reader)
    _, a = png_rows(before)
    _, b = png_rows(saved)
    _, c = png_rows(after)
    area = lambda rows: b"".join(bytes(row[48*4:360*4]) for row in rows[44:86])
    if area(a) == area(c) or area(b) != area(c):
        raise RuntimeError("Saved color, text size and keymap were not restored")
    saved_again = capture("saved-again", writer)
    reloaded_again = capture("reloaded-again", reader)
    _, d = png_rows(saved_again)
    _, e = png_rows(reloaded_again)
    if area(c) == area(e) or area(d) != area(e):
        raise RuntimeError("Updated settings were not overwritten and reloaded")
    DRIVE.unlink()
    subprocess.run([str(C1541), "-format", "GIZMO,01", "d64", str(DRIVE)],
                   cwd=ROOT, check=True, capture_output=True)
    keymap = build("KEYMAP", source="src/display_keymap_test.c")
    keymap_image = capture("keymap", keymap)
    _, pixels = png_rows(keymap_image)
    if pixels[30][30*4:30*4+3] != bytes((0, 0, 0)):
        raise RuntimeError("QWERTY/QWERTZ key mapping failed")
    print("Settings restored across restarts; Y/Z mapping including case verified")


if __name__ == "__main__":
    main()
