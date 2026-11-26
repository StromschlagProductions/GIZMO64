from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
root = Path(__file__).resolve().parents[1]
files = {
    'GIZMO64.PRG': root / 'GIZMO64.PRG',
    'gizmo_bridge.py': root / 'bridge/gizmo_bridge.py',
    'start-gizmo.bat': root / 'bridge/start-gizmo.bat',
    'config.example.json': root / 'bridge/config.example.json',
    'KURZANLEITUNG.md': root / 'docs/kurzanleitung-0.2.2.md',
}
with ZipFile(root / 'GIZMO64-v0.2.2.zip', 'w', ZIP_DEFLATED) as archive:
    for name, path in files.items():
        archive.write(path, name)
