import pathlib
import re
import subprocess

root = pathlib.Path(__file__).resolve().parents[1]
output = root / "build" / "charset.s"
subprocess.run(
    ["cc65", "-t", "c64", "-I", "src", "-o", str(output), "src/ui.c"],
    cwd=root,
    check=True,
)
assembly = output.read_text()
bytes_in_assembly = bytes(
    int(value, 16)
    for value in re.findall(r"\$([0-9A-F]{2})", assembly)
)
assert bytes([0x20, 0xC7, 0xC9, 0xDA, 0xCD, 0xCF]) in bytes_in_assembly
