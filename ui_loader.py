"""Load calculator UI from compressed blob or HTML file."""
from __future__ import annotations

import base64
import zlib
from pathlib import Path


def load_index_html(static_dir: Path) -> str:
    zpath = static_dir / "ui.zlib.b64"
    if zpath.exists():
        return zlib.decompress(base64.b64decode(zpath.read_text().strip().encode())).decode()
    chunks = sorted(static_dir.glob("ui.b64.*"), key=lambda p: p.name)
    if chunks:
        b64 = "".join(p.read_text().strip() for p in chunks)
        return base64.b64decode(b64.encode()).decode()
    path = static_dir / "index.html"
    if path.exists():
        return path.read_text()
    return "UI missing — deploy static/ui.zlib.b64"
