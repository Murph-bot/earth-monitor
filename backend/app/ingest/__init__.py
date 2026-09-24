"""Scheduled ingestion — a separate process from the web API (Phase 4).

`pipeline` does one sensor's work; `scheduler` decides when sensors run.
Entry point: `python -m app.ingest [--once]`.
"""
