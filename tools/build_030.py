"""Build the released C64 0.3.0 client with project-local tools."""
from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
CC65 = ROOT / ".local-tools/cc65/bin/cl65.exe"
PRG = ROOT / "GIZMO64.PRG"
MAP = ROOT / "build/GIZMO64.map"
SOURCES = (
    "src/main.c", "src/ui.c", "src/link.c", "src/font.s",
    "src/display_assets.s", "src/border_irq.s", "src/bitmap_blit.s",
    "src/keyboard_matrix.s",
)


def main() -> None:
    if not CC65.is_file():
        raise RuntimeError("Projektlokales cc65 fehlt")
    MAP.parent.mkdir(exist_ok=True)
    subprocess.run([sys.executable, "assets/build_display_assets.py"], cwd=ROOT, check=True)
    original_link = subprocess.run(
        ["git", "show", "v0.2.3:src/link.c"], cwd=ROOT,
        check=True, capture_output=True, text=True,
    ).stdout
    if (ROOT / "src/link.c").read_text() != original_link:
        raise RuntimeError("Kommunikationscode weicht von v0.2.3 ab")
    subprocess.run([
        str(CC65), "-t", "c64", "-O", "-I", "src", "-Wl", f"-m,{MAP}",
        "-o", str(PRG), *SOURCES,
    ], cwd=ROOT, check=True)
    matches = re.findall(
        r"^BSS\s+[0-9A-F]{6}\s+([0-9A-F]{6})\s+", MAP.read_text(), re.M,
    )
    if len(matches) != 1 or int(matches[0], 16) >= 0x8000:
        raise RuntimeError("BSS ueberlappt VIC-Bank ab $8000")
    data = PRG.read_bytes()
    if data[:2] != b"\x01\x08":
        raise RuntimeError("Ungueltige C64-Ladeadresse")
    print(f"GIZMO64.PRG: {len(data)} bytes, BSS ${int(matches[0],16):04X}, SHA256 {sha256(data).hexdigest()}")


if __name__ == "__main__":
    main()
