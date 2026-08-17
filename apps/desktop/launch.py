"""Source-tree desktop entry point used by the Windows shortcut."""

from __future__ import annotations

import os
import sys
from importlib import import_module
from pathlib import Path

if getattr(sys, "frozen", False):
    os.chdir(Path(sys.executable).resolve().parent)
else:
    ROOT = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(ROOT / "api"))
    sys.path.insert(0, str(ROOT / "desktop"))

def run_self_check() -> None:
    if getattr(sys, "frozen", False):
        bundle_root = Path(sys._MEIPASS)
        web_dist = bundle_root / "apps" / "web" / "dist"
        icon = bundle_root / "apps" / "desktop" / "assets" / "skinflow.ico"
    else:
        root = Path(__file__).resolve().parents[2]
        web_dist = root / "apps" / "web" / "dist"
        icon = root / "apps" / "desktop" / "assets" / "skinflow.ico"
    if not (web_dist / "index.html").is_file():
        raise RuntimeError(f"Missing bundled Web application: {web_dist}")
    if not icon.is_file():
        raise RuntimeError(f"Missing bundled desktop icon: {icon}")
    print("Skinflow portable self-check passed")


if __name__ == "__main__":
    if "--self-check" in sys.argv:
        run_self_check()
    else:
        launcher = import_module("skinflow_desktop.launcher")
        start_desktop = launcher.start_desktop
        start_desktop()
