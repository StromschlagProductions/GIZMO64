"""Build and optionally capture the isolated C64 display experiment."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess

from test_border_probe import png_rows

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "build"
CC65 = ROOT / ".local-tools/cc65/bin/cl65.exe"
VICE = ROOT / ".local-tools/vice/SDL2VICE-3.9-win64/x64sc.exe"
SOURCES = ["src/main_bitmap.c", "src/ui_bitmap.c", "src/link.c",
           "src/font.s", "src/display_assets.s", "src/border_irq.s"]


def run(*args: str, cwd: Path = ROOT) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=cwd, check=True, text=True, capture_output=True)


def build(name: str, defines: tuple[str, ...] = ()) -> tuple[Path, dict]:
    program = BUILD / f"GIZMO64-DISPLAY-{name}.PRG"
    listing = BUILD / f"GIZMO64-DISPLAY-{name}.map"
    args = [str(CC65), "-t", "c64", "-O", "-I", "src"]
    args += [f"-D{define}" for define in defines]
    args += ["-Wl", f"-m,{listing}", "-o", str(program), *SOURCES]
    run(*args)
    segments = {}
    segment_section = listing.read_text().split("Segment list:", 1)[1].split("Exports list", 1)[0]
    for line in segment_section.splitlines():
        match = re.match(r"^(\w+)\s+([0-9A-F]{6})\s+([0-9A-F]{6})\s+([0-9A-F]{6})", line)
        if match:
            segments[match[1]] = {"start": int(match[2], 16),
                                  "end": int(match[3], 16),
                                  "bytes": int(match[4], 16)}
    if not segments or segments["BSS"]["end"] >= 0x8000:
        raise RuntimeError("Program/BSS could overlap VIC bank 2")
    if program.read_bytes()[:2] != b"\x01\x08":
        raise RuntimeError("Invalid C64 PRG load address")
    return program, segments


def capture(program: Path, name: str, cycles: int = 30000000) -> Path:
    target = BUILD / f"display-{name}.png"
    log = BUILD / f"display-{name}.log"
    target.unlink(missing_ok=True)
    command = [str(VICE), "-VICIImodel", "6569", "-VICIIborders", "1",
               "-logfile", str(log), "-autostartprgmode", "1",
               "-autostart", str(program), "-exitscreenshot", str(target),
               "-limitcycles", str(cycles), "-silent"]
    result = subprocess.run(command, cwd=VICE.parent, timeout=120, check=False)
    if result.returncode not in (0, 1) or not target.is_file():
        raise RuntimeError(f"VICE capture failed: {name}, {result.returncode}")
    if log.is_file() and "cycle limit reached" not in log.read_text(errors="replace"):
        raise RuntimeError(f"VICE did not reach planned limit: {name}")
    data = target.read_bytes()
    if data[:8] != b"\x89PNG\r\n\x1a\n" or int.from_bytes(data[16:20], "big") != 408 or int.from_bytes(data[20:24], "big") != 293:
        raise RuntimeError(f"Unexpected screenshot dimensions: {name}")
    _, rows = png_rows(target)
    def green_pixels(y1: int, y2: int) -> int:
        return sum(1 for row in rows[y1:y2] for x in range(48, 360)
                   if row[x * 4 + 1] > 50 and row[x * 4 + 1] > row[x * 4])
    if green_pixels(8, 40) < 1000 or green_pixels(44, 225) < 5000:
        raise RuntimeError(f"Logo or full conversation not rendered: {name}")
    if green_pixels(250, 293) > 0:
        raise RuntimeError(f"Mirrored logo in lower border: {name}")
    return target


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--capture", action="store_true")
    args = parser.parse_args()
    BUILD.mkdir(exist_ok=True)
    run("python", "assets/build_display_assets.py")
    release_link = run("git", "show", "930a4ea:src/link.c").stdout
    if (ROOT / "src/link.c").read_text() != release_link:
        raise RuntimeError("Transport source differs from release v0.2.3")
    manifest = {"base_commit": "930a4ea", "transport_unchanged": True,
                "VIC_bank": "$8000-$bfff", "screen": "$8400",
                "sprites": "$8800", "bitmap": "$a000", "programs": {},
                "visible_conversation_rows": {"STANDARD": 22, "COMPACT": 26, "DENSE": 31},
                "screenshots": {}}
    variants = {"EXPERIMENT": (), "STANDARD": ("GIZMO_DEMO",),
                "COMPACT": ("GIZMO_DEMO", "GIZMO_DEMO_COMPACT"),
                "DENSE": ("GIZMO_DEMO", "GIZMO_DEMO_DENSE")}
    for name, defines in variants.items():
        program, segments = build(name, defines)
        manifest["programs"][name] = {"path": str(program.relative_to(ROOT)),
                                       "sha256": sha(program), "size_bytes": program.stat().st_size,
                                       "segments": segments}
        if args.capture and name != "EXPERIMENT":
            image = capture(program, name.lower())
            manifest["screenshots"][name] = {"path": str(image.relative_to(ROOT)),
                                              "sha256": sha(image), "size": "408x293"}
        print(name, program.stat().st_size, segments["BSS"]["end"])
    path = BUILD / "display-manifest.json"
    path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(path)


if __name__ == "__main__":
    main()
