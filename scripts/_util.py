"""CLI utilities."""

import sys


def configure_stdout() -> None:
    """Force UTF-8 stdout on Windows consoles."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure:
            try:
                reconfigure(encoding="utf-8")
            except Exception:
                pass
