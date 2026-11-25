from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
root = Path(__file__).resolve().parent
with ZipFile(root.parent / 'GIZMO-LAB-v0.2.zip', 'w', ZIP_DEFLATED) as z:
    for name in ('gizmo_lab.py', 'memory.py', 'start-gizmo-lab.bat', 'config.example.json', 'personality.example.txt', 'questions.json', 'variants.example.json', 'README.md', 'MEMORY.md', 'WINDOWS-TESTPLAN.md', 'test_lab.py', 'test_memory.py', 'package.py'):
        z.write(root / name, name)
    z.write(root / 'README.md', 'KURZANLEITUNG.md')
