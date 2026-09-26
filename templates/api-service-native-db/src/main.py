"""Service entrypoint: bootstrap → wire → serve → teardown."""

from __future__ import annotations

import uvicorn

from app.api import create_app
from app.bootstrap import init, teardown


# ─── BOOTSTRAP ────────────────────────────────────────────────────────────────
float_start_time = init()

# ─── WIRE ─────────────────────────────────────────────────────────────────────
app = create_app()

# ─── RUN ──────────────────────────────────────────────────────────────────────
# Blocks until the process receives a shutdown signal (SIGINT/SIGTERM).
if __name__ == "__main__":
	uvicorn.run(app, host="0.0.0.0", port=8000)  # noqa: S104 -- container-friendly bind
	teardown(float_start_time)
