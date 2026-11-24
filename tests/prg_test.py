from pathlib import Path

program = Path("GIZMO64.PRG").read_bytes()
assert program[:2] == b"\x01\x08"
assert bytes.fromhex("c7 c9 da cd cf") in program  # GIZMO in cc65 PETSCII
assert bytes.fromhex("c1 d4 c4 d4 20") in program  # ATDT in cc65 PETSCII
assert bytes.fromhex("d0 c9 ce c7 00") in program  # PING in cc65 PETSCII
assert b"ATDT " not in program
