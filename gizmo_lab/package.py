from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
root = Path(__file__).resolve().parent
with ZipFile(root.parent / 'GIZMO-LAB-v0.1.zip', 'w', ZIP_DEFLATED) as z:
    for name in ('gizmo_lab.py', 'start-gizmo-lab.bat', 'config.example.json', 'personality.example.txt', 'questions.json', 'README.md', 'test_lab.py', 'package.py'):
        z.write(root / name, name)
