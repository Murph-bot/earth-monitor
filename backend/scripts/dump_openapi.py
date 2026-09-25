"""Dump the live OpenAPI spec — the generated client's source of truth.

Usage: uv run python scripts/dump_openapi.py  (from backend/)
"""

import json
from pathlib import Path

from app.main import create_app

OUT = Path(__file__).parents[2] / "packages" / "shared" / "openapi.json"

if __name__ == "__main__":
    spec = create_app().openapi()
    OUT.write_text(json.dumps(spec, indent=2) + "\n")
    print(f"wrote {OUT} — {len(spec['paths'])} paths")
