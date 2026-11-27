"""VICE input and rendering checks for the character-mode hardware candidate."""
from pathlib import Path
import argparse
import subprocess
from test_border_probe import png_rows

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "build"
VICE = ROOT / ".local-tools/vice/SDL2VICE-3.9-win64/x64sc.exe"
DRIVE = BUILD / "text-test.d64"
C1541 = VICE.parent / "c1541.exe"


def capture(name: str, program: str, keys: str) -> Path:
    image = BUILD / f"text-{name}.png"
    image.unlink(missing_ok=True)
    args = [str(VICE), "-VICIImodel", "6569", "-VICIIborders", "1",
            "-8", str(DRIVE)]
    if keys:
        args += ["-keybuf", keys]
    args += ["-autostartprgmode", "1", "-autostart", str(BUILD / program),
             "-exitscreenshot", str(image), "-limitcycles", "30000000", "-silent"]
    result = subprocess.run(args, cwd=VICE.parent, timeout=120)
    if result.returncode not in (0, 1) or not image.is_file():
        raise RuntimeError(f"VICE capture failed: {name}")
    return image


def crop(path: Path, x1: int, x2: int, y1: int, y2: int) -> bytes:
    width, rows = png_rows(path)
    if (width, len(rows)) != (408, 293):
        raise RuntimeError(f"Wrong geometry: {path}")
    return b"".join(bytes(row[x1*4:x2*4]) for row in rows[y1:y2])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reuse", action="store_true")
    reuse = parser.parse_args().reuse
    if not reuse:
        DRIVE.unlink(missing_ok=True)
        subprocess.run([str(C1541), "-format", "GIZMO,02", "d64", str(DRIVE)],
                       cwd=ROOT, capture_output=True, check=True)
    cases = {
        "demo": ("GIZMO64-TEXT-DEMO.PRG", ""),
        "f2": ("GIZMO64-TEXT-DEMO.PRG", r"\x89"),
        "f4": ("GIZMO64-TEXT-COMPACT.PRG", r"\x8a"),
        "f6": ("GIZMO64-TEXT-DEMO.PRG", r"\x8b"),
        "f8": ("GIZMO64-TEXT-DEMO.PRG", r"\x8c"),
        "menu": ("GIZMO64-TEXT-DEMO.PRG", r"HELP\x0d\x11\x11\x0d"),
        "mapped": ("GIZMO64-TEXT-DEMO.PRG", r"HELP\x0d\x11\x11\x0d\x8c\x8cYZ"),
        "direct": ("GIZMO64-TEXT-DEMO.PRG", r"ZY"),
    }
    images = {name: BUILD / f"text-{name}.png" if reuse else capture(name, *case)
              for name, case in cases.items()}
    dialog = lambda path: crop(path, 48, 360, 76, 212)
    if dialog(images["f2"]) == dialog(images["demo"]):
        raise RuntimeError("F2 did not switch the character font")
    if dialog(images["f4"]) != dialog(images["demo"]):
        raise RuntimeError("F4 did not restore the standard font")
    if crop(images["f6"], 48, 360, 8, 40) == crop(images["demo"], 48, 360, 8, 40):
        raise RuntimeError("F6 did not switch to the safe logo")
    if dialog(images["f8"]) == dialog(images["demo"]):
        raise RuntimeError("F8 did not open service")
    if crop(images["menu"], 48, 360, 92, 100) == crop(images["demo"], 48, 360, 92, 100):
        raise RuntimeError("Menu did not change selection")
    if crop(images["mapped"], 48, 104, 220, 228) != crop(images["direct"], 48, 104, 220, 228):
        raise RuntimeError("QWERTZ input YZ did not match direct ZY")
    print("Text mode: F2/F4, F6, F8, menu and QWERTZ input verified in VICE")


if __name__ == "__main__":
    main()
