"""SQLite persistence, so repeated runs dedupe leads and keep their review/sent status."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path

from .models import Lead

SCHEMA = """
CREATE TABLE IF NOT EXISTS leads (
  id TEXT PRIMARY KEY,
  data TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'new',
  first_seen TEXT NOT NULL,
  updated TEXT NOT NULL
);
"""


class Store:
    def __init__(self, path: str | Path):
        self.db = sqlite3.connect(path)
        self.db.execute(SCHEMA)

    def get(self, lead_id: str) -> Lead | None:
        row = self.db.execute("SELECT data, status FROM leads WHERE id=?", (lead_id,)).fetchone()
        if not row:
            return None
        lead = Lead.from_dict(json.loads(row[0]))
        lead.status = row[1]
        return lead

    def upsert(self, lead: Lead) -> None:
        now = datetime.now().isoformat(timespec="seconds")
        self.db.execute(
            "INSERT INTO leads (id, data, status, first_seen, updated) VALUES (?,?,?,?,?) "
            "ON CONFLICT(id) DO UPDATE SET data=excluded.data, updated=excluded.updated",
            (lead.id, json.dumps(lead.to_dict(), ensure_ascii=False), lead.status, now, now))
        self.db.commit()

    def set_status(self, lead_id: str, status: str) -> bool:
        cur = self.db.execute("UPDATE leads SET status=?, updated=? WHERE id=?",
                              (status, datetime.now().isoformat(timespec="seconds"), lead_id))
        self.db.commit()
        return cur.rowcount > 0

    def all(self) -> list[Lead]:
        out = []
        for data, status in self.db.execute("SELECT data, status FROM leads"):
            lead = Lead.from_dict(json.loads(data))
            lead.status = status
            out.append(lead)
        return sorted(out, key=lambda l: -l.score)
