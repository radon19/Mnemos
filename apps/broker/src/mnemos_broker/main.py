"""Uvicorn entry point. Configuration comes from the environment only."""

from __future__ import annotations

from .app import create_app

app = create_app()
