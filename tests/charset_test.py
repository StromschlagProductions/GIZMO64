import pathlib
import re
import subprocess
import shutil

root = pathlib.Path(__file__).resolve().parents[1]
compiler = root / '.local-tools' / 'cc65' / 'bin' / 'cc65.exe'
compiler = str(compiler) if compiler.is_file() else shutil.which('cc65')
assert compiler, 'cc65 compiler not found'
output = root / "build" / "charset.s"
subprocess.run(
    [compiler, "-t", "c64", "-I", "src", "-o", str(output), "src/ui.c"],
    cwd=root,
    check=True,
)
assembly = output.read_text()
bytes_in_assembly = bytes(
    int(value, 16)
    for value in re.findall(r"\$([0-9A-F]{2})", assembly)
)
assert bytes([0x59, 0x4f, 0x55, 0x3a]) not in bytes_in_assembly
assert bytes([0xd9, 0xcf, 0xd5, 0x3a]) in bytes_in_assembly  # YOU: in PETSCII

punctuation_source = root / "build" / "punctuation.c"
punctuation_assembly = root / "build" / "punctuation.s"
punctuation_source.write_text('const unsigned char punctuation[] = "?!,.:;\\\"\'()-=/";\n')
subprocess.run([compiler, "-t", "c64", "-o", str(punctuation_assembly),
                str(punctuation_source)], check=True)
assert "$3F,$21,$2C,$2E,$3A,$3B,$22,$27,$28,$29,$2D,$3D,$2F,$00" in punctuation_assembly.read_text()
