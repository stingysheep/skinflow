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

launcher = import_module("skinflow_desktop.launcher")
start_desktop = launcher.start_desktop


def run_self_check() -> None:
    from skinflow_api.main import _web_dist_path

    web_dist = _web_dist_path()
    icon = launcher.desktop_icon_path()
    if not (web_dist / "index.html").is_file():
        raise RuntimeError(f"Missing bundled Web application: {web_dist}")
    if not icon.is_file():
        raise RuntimeError(f"Missing bundled desktop icon: {icon}")
    print("Skinflow portable self-check passed")


if __name__ == "__main__":
    if "--self-check" in sys.argv:
        run_self_check()
    else:
        start_desktop()
