"""Source-tree desktop entry point used by the Windows shortcut."""

from __future__ import annotations

import sys
from importlib import import_module
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "api"))
sys.path.insert(0, str(ROOT / "desktop"))

start_desktop = import_module("skinflow_desktop.launcher").start_desktop


if __name__ == "__main__":
    start_desktop()
