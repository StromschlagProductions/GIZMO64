"""Reproducible isolated top-border comparison in x64sc, no GIZMO engine."""
from __future__ import annotations

import json
from pathlib import Path
import struct
import subprocess
import zlib

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "build"
BIN = ROOT / ".local-tools/cc65/bin"
VICE = ROOT / ".local-tools/vice/SDL2VICE-3.9-win64/x64sc.exe"


def run(*args: str, cwd: Path = ROOT, good: tuple[int, ...] = (0,)) -> None:
    result = subprocess.run(args, cwd=cwd, timeout=60, check=False)
    if result.returncode not in good:
        raise RuntimeError(f"Command failed ({result.returncode}): {args}")


def png_rows(path: Path) -> tuple[int, list[bytearray]]:
    """Decode 8-bit RGBA PNG rows using only the Python standard library."""
    data = path.read_bytes()
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("Not a PNG")
    pos, chunks = 8, []
    while pos < len(data):
        size = int.from_bytes(data[pos:pos + 4], "big")
        kind = data[pos + 4:pos + 8]
        content = data[pos + 8:pos + 8 + size]
        pos += size + 12
        if kind == b"IHDR":
            width, height, depth, color, *_ = struct.unpack(">IIBBBBB", content)
        elif kind == b"IDAT":
            chunks.append(content)
        elif kind == b"IEND":
            break
    if depth != 8 or color != 6:
        raise ValueError("Unsupported PNG format")
    raw = zlib.decompress(b"".join(chunks))
    stride = width * 4
    previous = bytearray(stride)
    offset = 0
    rows = []
    for row_index in range(height):
        filtering = raw[offset]
        row = bytearray(raw[offset + 1:offset + 1 + stride])
        offset += stride + 1
        for i in range(stride):
            left = row[i - 4] if i >= 4 else 0
            above = previous[i]
            upper_left = previous[i - 4] if i >= 4 else 0
            if filtering == 1:
                row[i] = (row[i] + left) & 255
            elif filtering == 2:
                row[i] = (row[i] + above) & 255
            elif filtering == 3:
                row[i] = (row[i] + ((left + above) // 2)) & 255
            elif filtering == 4:
                predictor = left + above - upper_left
                distances = (abs(predictor - left), abs(predictor - above),
                             abs(predictor - upper_left))
                chosen = (left, above, upper_left)[distances.index(min(distances))]
                row[i] = (row[i] + chosen) & 255
            elif filtering != 0:
                raise ValueError(f"Unsupported PNG filter {filtering}")
        previous = row
        rows.append(row)
    return width, rows


def pixel(path: Path, x: int, y: int) -> tuple[int, int, int]:
    width, rows = png_rows(path)
    if x >= width or y >= len(rows):
        raise ValueError("Pixel outside image")
    return tuple(rows[y][x * 4:x * 4 + 3])


def main() -> None:
    BUILD.mkdir(exist_ok=True)
    programs = {}
    for variant, flags in (("base", ["-D", "BORDER_PROBE_NO_IRQ"]),
                           ("irq", [])):
        obj = BUILD / f"border-probe-{variant}.o"
        prg = BUILD / f"BORDER-PROBE-{variant.upper()}.PRG"
        run(str(BIN / "ca65.exe"), *flags, "-o", str(obj), "src/border_probe.s")
        run(str(BIN / "ld65.exe"), "-C", "tools/border-probe.cfg",
            "-o", str(prg), str(obj))
        programs[variant] = prg
    if programs["base"].read_bytes() == programs["irq"].read_bytes():
        raise RuntimeError("Assembler variants did not differ")
    observations = {}
    for model in ("6569", "8565"):
        for borders, label, dimensions in (("1", "full", (408, 293)),
                                            ("2", "debug", (504, 312))):
            for variant, prg in programs.items():
                target = BUILD / f"border-probe-{model}-{label}-{variant}.png"
                target.unlink(missing_ok=True)
                run(str(VICE), "-VICIImodel", model, "-VICIIborders", borders,
                    "-autostartprgmode", "1", "-autostart", str(prg),
                    "-exitscreenshot", str(target), "-limitcycles", "4000000",
                    "-silent", cwd=VICE.parent, good=(0, 1))
                data = target.read_bytes()
                if struct.unpack(">II", data[16:24]) != dimensions:
                    raise RuntimeError(f"Unexpected VICE capture: {target}")
                observations[f"{model}_{label}_{variant}"] = str(target.relative_to(ROOT))
            if label == "full":
                closed = BUILD / f"border-probe-{model}-full-base.png"
                opened = BUILD / f"border-probe-{model}-full-irq.png"
                if pixel(closed, 250, 10) != (0, 0, 0):
                    raise RuntimeError(f"Closed border was not black: {model}")
                if pixel(opened, 250, 10) == (0, 0, 0):
                    raise RuntimeError(f"Border did not open: {model}")
                if pixel(opened, 190, 2) != (255, 255, 255):
                    raise RuntimeError(f"Top-border sprite is missing: {model}")
                print(model, "top border and sprite verified")
    (BUILD / "border-probe-manifest.json").write_text(
        json.dumps({"emulator": "x64sc", "sprite_count": 1,
                    "models": ["6569", "8565"], "screenshots": observations},
                   indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
