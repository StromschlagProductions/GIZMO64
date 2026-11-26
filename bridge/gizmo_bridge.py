"""Compatibility import for the C64 transport now owned by LAB.

Use the Control Center or its terminal starter. This module never starts a
second model process or opens a separate memory store.
"""
import sys
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'gizmo_lab'))
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
try:
    from gizmo_lab.gizmo_lab import Uplink, c64_records, UPLINK_BEGIN, UPLINK_PARA, UPLINK_END
except ModuleNotFoundError:
    from gizmo_lab import Uplink, c64_records, UPLINK_BEGIN, UPLINK_PARA, UPLINK_END


if __name__=='__main__':
    raise SystemExit('Start GIZMO with GIZMO.cmd and enable COMMODORE UPLINK in SETTINGS.')
