"""Create and verify the C64 0.3.0 release archive."""
from hashlib import sha256
from pathlib import Path
from zipfile import ZipFile, ZipInfo, ZIP_DEFLATED

ROOT = Path(__file__).resolve().parents[1]
PRG = ROOT / "GIZMO64.PRG"
GUIDE = ROOT / "docs/kurzanleitung-0.3.0.md"
OUT = ROOT / "GIZMO64-v0.3.0.zip"


def add(archive: ZipFile, name: str, content: bytes) -> None:
    info = ZipInfo(name, (2026, 11, 27, 0, 0, 0))
    info.compress_type = ZIP_DEFLATED
    archive.writestr(info, content)


def main() -> None:
    program = PRG.read_bytes()
    if program[:2] != b"\x01\x08":
        raise RuntimeError("Ungueltiges PRG")
    digest = sha256(program).hexdigest()
    with ZipFile(OUT, "w") as archive:
        add(archive, "GIZMO64.PRG", program)
        add(archive, "KURZANLEITUNG.md", GUIDE.read_bytes())
        add(archive, "SHA256.txt", f"{digest}  GIZMO64.PRG\n".encode("ascii"))
    with ZipFile(OUT) as archive:
        if archive.namelist() != ["GIZMO64.PRG", "KURZANLEITUNG.md", "SHA256.txt"]:
            raise RuntimeError("Unerwarteter Paketinhalt")
        if archive.read("GIZMO64.PRG") != program:
            raise RuntimeError("Paketpruefung fehlgeschlagen")
    print(f"{OUT}: SHA256 {sha256(OUT.read_bytes()).hexdigest()}")


if __name__ == "__main__":
    main()
