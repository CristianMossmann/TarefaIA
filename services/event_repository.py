from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime
from pathlib import Path


class EventRepository:
    def __init__(self, db_path: Path):
        self.db_path = db_path

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self) -> None:
        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS events (
                    id TEXT PRIMARY KEY,
                    event_time TEXT,
                    label TEXT,
                    confidence REAL,
                    image_path TEXT
                )
                """
            )
            conn.commit()

    def save_event(self, label: str, confidence: float, image_path: str) -> dict:
        event_id = str(uuid.uuid4())[:8]
        event_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO events (id, event_time, label, confidence, image_path)
                VALUES (?, ?, ?, ?, ?)
                """,
                (event_id, event_time, label, confidence, image_path),
            )
            conn.commit()

        return {
            "id": event_id,
            "event_time": event_time,
            "label": label,
            "confidence": confidence,
            "image_path": image_path,
        }

    def list_events(self, limit: int = 50) -> list[dict]:
        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT id, event_time, label, confidence, image_path
                FROM events
                ORDER BY event_time DESC
                LIMIT ?
                """,
                (limit,),
            )
            rows = cur.fetchall()

        return [dict(row) for row in rows]

    def count_events(self) -> int:
        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(1) AS total FROM events")
            row = cur.fetchone()
        return int(row["total"] if row else 0)
