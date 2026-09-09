"""ASGI entrypoint: materialize UI then serve FastAPI app."""
from decode_ui import write_index
write_index()
from app import app  # noqa: E402
