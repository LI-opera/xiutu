"""Timing barriers ONLY for isolated WP08 integration child processes."""

import os
import time
from pathlib import Path

import app.mcp_server.main as server
from app.tools.manual_tools import ManualTools


def pause():
    gate = Path(os.environ["WP08_GATE"])
    (gate / "ready").write_text("real service reached barrier", encoding="utf8")
    deadline = time.monotonic() + 8
    while not (gate / "go").exists():
        if time.monotonic() >= deadline:
            raise RuntimeError("WP08 test barrier deadline")
        time.sleep(0.01)


def create_app():
    # No production hook, replacement authorization, source result or fake DB.
    if os.environ["WP08_WINDOW"] == "owner_lock":
        original = ManualTools.execute

        def execute(self, *args, **kwargs):
            data = original(self, *args, **kwargs)
            pause()
            return data

        ManualTools.execute = execute
    else:
        original = server.validate_result

        def validate(*args, **kwargs):
            pause()
            return original(*args, **kwargs)

        server.validate_result = validate
    return server.create_app()
