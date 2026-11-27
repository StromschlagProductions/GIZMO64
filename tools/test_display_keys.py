"""End-to-end VICE check of palette, font size, scrollback, and fallback."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess

from test_border_probe import png_rows

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "build"
VICE = ROOT / ".local-tools/vice/SDL2VICE-3.9-win64/x64sc.exe"


def capture(name: str, program: str, keys: str) -> Path:
    target = BUILD / f"display-{name}.png"
    target.unlink(missing_ok=True)
    command = [str(VICE), "-VICIImodel", "6569", "-VICIIborders", "1",
               "-keybuf", keys, "-autostartprgmode", "1", "-autostart",
               str(BUILD / program), "-exitscreenshot", str(target),
               "-limitcycles", "30000000", "-silent"]
    result = subprocess.run(command, cwd=VICE.parent, timeout=120, check=False)
    if result.returncode not in (0, 1) or not target.is_file():
        raise RuntimeError(f"VICE key capture failed: {name}")
    return target


def conversation(path: Path) -> bytes:
    width, rows = png_rows(path)
    if (width, len(rows)) != (408, 293):
        raise RuntimeError(f"Wrong screenshot geometry: {path}")
    return b"".join(bytes(row[48 * 4:360 * 4]) for row in rows[44:225])


def green_count(rows: list[bytearray], y1: int, y2: int) -> int:
    return sum(1 for row in rows[y1:y2] for x in range(48, 360)
               if row[x * 4 + 1] > 50 and row[x * 4 + 1] > row[x * 4])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reuse", action="store_true",
                        help="Validate existing captures without rerunning VICE")
    args = parser.parse_args()
    cases = {"f2-switch": ("GIZMO64-DISPLAY-STANDARD.PRG", r"\x89"),
             "f4-switch": ("GIZMO64-DISPLAY-DENSE.PRG", r"\x8a"),
             "f6-fallback": ("GIZMO64-DISPLAY-STANDARD.PRG", r"\x8b"),
             "f1-ice": ("GIZMO64-DISPLAY-STANDARD.PRG", r"\x85"),
             "f3-back": ("GIZMO64-DISPLAY-STANDARD.PRG", r"\x86"),
             "f3-f5-next": ("GIZMO64-DISPLAY-STANDARD.PRG", r"\x86\x87"),
             "f3-f7-live": ("GIZMO64-DISPLAY-STANDARD.PRG", r"\x86\x88"),
             "f8-service": ("GIZMO64-DISPLAY-STANDARD.PRG", r"\x8c"),
             "help-command": ("GIZMO64-DISPLAY-STANDARD.PRG", r"HELP\x0d"),
             "menu-keyboard": ("GIZMO64-DISPLAY-STANDARD.PRG", r"HELP\x0d\x11\x11\x0d"),
             "menu-qwertz-input": ("GIZMO64-DISPLAY-STANDARD.PRG", r"HELP\x0d\x11\x11\x0d\x8c\x8cYZ")}
    images = {name: BUILD / f"display-{name}.png" if args.reuse else
              capture(name, program, keys)
              for name, (program, keys) in cases.items()}
    reference = conversation(BUILD / "display-compact.png")
    for key in ("f2-switch", "f4-switch"):
        if conversation(images[key]) != reference:
            raise RuntimeError(f"{key} did not restore the COMPACT conversation")
    _, rows = png_rows(images["f6-fallback"])
    if green_count(rows, 8, 40) != 0 or green_count(rows, 44, 68) < 1000:
        raise RuntimeError("F6 did not move the logo into the display area")
    if green_count(rows, 68, 225) < 5000:
        raise RuntimeError("F6 lost the conversation")
    standard = conversation(BUILD / "display-standard.png")
    if conversation(images["f3-back"]) == standard:
        raise RuntimeError("F3 did not change the scroll position")
    for key in ("f3-f5-next", "f3-f7-live"):
        if conversation(images[key]) != standard:
            raise RuntimeError(f"{key} did not restore the live conversation")
    _, ice_rows = png_rows(images["f1-ice"])
    colors = {tuple(row[x * 4:x * 4 + 3])
              for row in ice_rows[44:225] for x in range(48, 360)}
    if (135, 240, 203) not in colors or (94, 214, 56) in colors:
        raise RuntimeError("F1 did not change the text to ice blue")
    for name, maximum in (("f8-service", 2500), ("help-command", 5000)):
        _, menu_rows = png_rows(images[name])
        count = green_count(menu_rows, 44, 225)
        if count >= maximum or count < 500:
            raise RuntimeError(f"{name} did not show its distinct view")
    _, menu_rows = png_rows(images["menu-keyboard"])
    if green_count(menu_rows, 76, 84) < 1000:
        raise RuntimeError("Cursor/RETURN did not select inverse KEYBOARD row")
    _, mapped_rows = png_rows(images["menu-qwertz-input"])
    font = (ROOT / "assets/display-prototype.bin").read_bytes()
    for char, screen_x in ((26, 88), (25, 96)):  # Z then Y in the input line
        # VICE's exit frame can capture the first scanline during a cursor redraw.
        for row in range(1, 7):
            mask = font[char*8+row]
            for bit in range(8):
                actual = mapped_rows[227+row][(screen_x+bit)*4+1] > 50
                if actual != bool(mask & (0x80 >> bit)):
                    raise RuntimeError("QWERTZ did not map typed YZ to ZY")
    result = {name: {"path": str(path.relative_to(ROOT)),
                     "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
              for name, path in images.items()}
    (BUILD / "display-key-manifest.json").write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print("Palette, size, scrollback, fallback, service, menu and QWERTZ verified in VICE")


if __name__ == "__main__":
    main()
