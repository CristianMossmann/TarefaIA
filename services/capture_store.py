from __future__ import annotations

from pathlib import Path


class CaptureStore:
    def __init__(self, captures_dir: Path):
        self.captures_dir = captures_dir

    def list_recent(self, limit: int = 20) -> list[dict]:
        if not self.captures_dir.exists():
            return []

        files = sorted(
            self.captures_dir.glob("*.jpg"), key=lambda p: p.stat().st_mtime, reverse=True
        )[:limit]

        return [
            {
                "name": f.name,
                "image_path": f"/static/captures/{f.name}",
            }
            for f in files
        ]
