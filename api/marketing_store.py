"""Marketing Analysis persistence (``research.marketing_analyses``) + snapshot bootstrap."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from api.db import ApiDB

SNAPSHOT = Path(__file__).resolve().parents[1] / "config" / "marketing_snapshot.json"

SQL = """
CREATE SCHEMA IF NOT EXISTS research;
CREATE TABLE IF NOT EXISTS research.marketing_analyses (
    id          VARCHAR PRIMARY KEY,
    company     VARCHAR NOT NULL,
    company_name VARCHAR,
    mode        VARCHAR,
    status      VARCHAR NOT NULL,
    stage       VARCHAR,
    result      JSON,
    evidence    JSON,
    error       VARCHAR,
    is_snapshot BOOLEAN DEFAULT false,
    created_at  TIMESTAMPTZ NOT NULL,
    completed_at TIMESTAMPTZ
);
"""


def bootstrap(db: ApiDB, snapshot: Path = SNAPSHOT) -> int:
    db.execute(SQL)
    db.execute(
        "UPDATE research.marketing_analyses SET status='failed', error='The API restarted before this "
        "analysis finished.' WHERE status IN ('queued','running')"
    )
    if not snapshot.exists():
        return 0
    data = json.loads(snapshot.read_text(encoding="utf-8"))
    # The committed snapshot is the source of truth for captured analyses: refresh on every boot.
    db.execute("DELETE FROM research.marketing_analyses WHERE is_snapshot")
    n = 0
    for a in data.get("analyses", []):
        if db.query_one("SELECT id FROM research.marketing_analyses WHERE id=?", [a["id"]]):
            continue
        db.execute(
            """INSERT INTO research.marketing_analyses
               (id, company, company_name, mode, status, stage, result, evidence, is_snapshot, created_at,
                completed_at) VALUES (?, ?, ?, ?, 'completed', 'Done', ?, ?, true, ?, ?)""",
            [a["id"], a["company"], a.get("company_name"), a.get("mode", "rule"), json.dumps(a["result"]),
             json.dumps(a["evidence"]), a["created_at"], a.get("completed_at") or a["created_at"]],
        )
        n += 1
    return n


def _row(r: dict[str, Any], full: bool) -> dict[str, Any]:
    out = {k: r.get(k) for k in ("id", "company", "company_name", "mode", "status", "stage", "error",
                                 "is_snapshot", "created_at", "completed_at")}
    for k in ("created_at", "completed_at"):
        if isinstance(out[k], datetime):
            out[k] = out[k].isoformat()
    if full:
        for k in ("result", "evidence"):
            v = r.get(k)
            out[k] = json.loads(v) if isinstance(v, str) else v
    return out


def create(db: ApiDB, aid: str, company: str, name: str) -> None:
    db.execute(
        """INSERT INTO research.marketing_analyses (id, company, company_name, status, stage, created_at)
           VALUES (?, ?, ?, 'queued', 'Queued', ?)""",
        [aid, company, name, datetime.now(UTC)],
    )


def set_stage(db: ApiDB, aid: str, stage: str) -> None:
    db.execute("UPDATE research.marketing_analyses SET status='running', stage=? WHERE id=?", [stage, aid])


def complete(db: ApiDB, aid: str, mode: str, result: dict, evidence: list) -> None:
    db.execute(
        """UPDATE research.marketing_analyses SET status='completed', stage='Done', mode=?, result=?,
           evidence=?, completed_at=? WHERE id=?""",
        [mode, json.dumps(result, default=str), json.dumps(evidence, default=str), datetime.now(UTC), aid],
    )


def fail(db: ApiDB, aid: str, msg: str) -> None:
    db.execute("UPDATE research.marketing_analyses SET status='failed', stage='Failed', error=?, "
               "completed_at=? WHERE id=?", [msg, datetime.now(UTC), aid])


def get(db: ApiDB, aid: str) -> dict[str, Any] | None:
    r = db.query_one("SELECT * FROM research.marketing_analyses WHERE id=?", [aid])
    return _row(r, True) if r else None


def list_(db: ApiDB, company: str | None = None) -> list[dict[str, Any]]:
    sql = ("SELECT id, company, company_name, mode, status, stage, error, is_snapshot, created_at, completed_at "
           "FROM research.marketing_analyses")
    params: list[Any] = []
    if company:
        sql += " WHERE company=?"
        params.append(company)
    return [_row(r, False) for r in db.query(sql + " ORDER BY created_at DESC LIMIT 100", params)]


def counts(db: ApiDB) -> dict[str, int]:
    try:
        return {"marketing_analyses": int(db.scalar("SELECT count(*) FROM research.marketing_analyses")),
                "research_runs": int(db.scalar("SELECT count(*) FROM research.research_runs"))}
    except Exception:
        return {}
