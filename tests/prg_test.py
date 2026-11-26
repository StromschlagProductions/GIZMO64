from pathlib import Path
import os

program = Path(os.environ.get("GIZMO_PRG_PATH", "GIZMO64.PRG")).read_bytes()
assert program[:2] == b"\x01\x08"
assert Path("assets/gizmo-font.bin").read_bytes() in program  # actual custom RAM charset
assert bytes.fromhex("c1 d4 c4 d4 20") in program  # ATDT in cc65 PETSCII
assert bytes.fromhex("d0 c9 ce c7 00") in program  # PING in cc65 PETSCII
assert b"ATDT " not in program
