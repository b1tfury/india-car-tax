"""Decode UI at build/start time."""
from __future__ import annotations
import base64, zlib
from pathlib import Path
from ui_chunks_a import PART_A
from ui_chunks_b import PART_B

def write_index(static_dir: Path | None = None) -> Path:
    static_dir = static_dir or Path(__file__).resolve().parent / "static"
    static_dir.mkdir(exist_ok=True)
    out = static_dir / "index.html"
    data = zlib.decompress(base64.b64decode("".join(PART_A + PART_B).encode()))
    out.write_bytes(data)
    return out

if __name__ == "__main__":
    p = write_index()
    print("wrote", p, "bytes", p.stat().st_size)
