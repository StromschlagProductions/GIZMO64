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

punctuation_source = root / "build" / "punctuation.c"
punctuation_assembly = root / "build" / "punctuation.s"
punctuation_source.write_text('const unsigned char punctuation[] = "?!,.:;\\\"\'()-=/";\n')
subprocess.run(["cc65", "-t", "c64", "-o", str(punctuation_assembly),
                str(punctuation_source)], check=True)
assert "$3F,$21,$2C,$2E,$3A,$3B,$22,$27,$28,$29,$2D,$3D,$2F,$00" in punctuation_assembly.read_text()
