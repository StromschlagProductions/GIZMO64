from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
root = Path(__file__).resolve().parent
with ZipFile(root.parent / 'GIZMO-LAB-v0.3.zip', 'w', ZIP_DEFLATED) as z:
    for name in ('gizmo_lab.py', 'memory.py', 'analysis.py', 'start-gizmo-lab.bat', 'config.example.json', 'personality.example.txt', 'questions.json', 'variants.example.json', 'README.md', 'MEMORY.md', 'WINDOWS-TESTPLAN.md', 'ARCHITEKTUR-0.3.md', 'WINDOWS-TESTPLAN-0.3.md', 'test_lab.py', 'test_memory.py', 'test_analysis.py', 'package.py'):
        z.write(root / name, name)
    z.write(root / 'README.md', 'KURZANLEITUNG.md')
