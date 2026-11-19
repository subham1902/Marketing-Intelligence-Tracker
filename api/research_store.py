"""Research persistence (DuckDB ``research`` schema).

Kept separate from the competitor ``raw.signals`` pipeline: general industry
findings are not tracked-page changes. Tables are created idempotently at API
startup so an existing warehouse gains them without reseeding.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from api.db import ApiDB

RESEARCH_SCHEMA_SQL = """
CREATE SCHEMA IF NOT EXISTS research;

CREATE TABLE IF NOT EXISTS research.research_runs (
    id                 VARCHAR PRIMARY KEY,
    objective          VARCHAR NOT NULL,
    industry           VARCHAR,
    geography          VARCHAR,
    time_window        VARCHAR,
    date_from          DATE,
    date_to            DATE,
    companies          JSON,
    source_preferences JSON,
    status             VARCHAR NOT NULL,   -- queued | running | completed | partial | failed
    provider           VARCHAR NOT NULL,   -- context.dev | demo
    is_demo            BOOLEAN DEFAULT false,
    provider_request_id VARCHAR,
    created_at         TIMESTAMPTZ NOT NULL,
    started_at         TIMESTAMPTZ,
    completed_at       TIMESTAMPTZ,
    error_code         VARCHAR,
    error_message      VARCHAR,
    result             JSON
);

CREATE TABLE IF NOT EXISTS research.research_sources (
    id              VARCHAR PRIMARY KEY,
    research_run_id VARCHAR NOT NULL,
    url             VARCHAR NOT NULL,
    domain          VARCHAR,
    title           VARCHAR,
    source_type     VARCHAR,
    published_at    TIMESTAMPTZ,
    retrieved_at    TIMESTAMPTZ,
    snippet         VARCHAR
);

CREATE TABLE IF NOT EXISTS research.research_findings (
    id              VARCHAR PRIMARY KEY,
    research_run_id VARCHAR NOT NULL,
    title           VARCHAR NOT NULL,
    category        VARCHAR NOT NULL,
    entity          VARCHAR,
    industry        VARCHAR,
    summary         VARCHAR,
    significance    INTEGER,
    confidence      DOUBLE,
    kind            VARCHAR NOT NULL,   -- verified_fact | analysis
    event_date      VARCHAR,
    source_ids      JSON,
    flags           JSON,
    created_at      TIMESTAMPTZ NOT NULL
);
"""


def bootstrap(db: ApiDB) -> None:
    db.execute(RESEARCH_SCHEMA_SQL)
    # A restart mid-run would leave a spinner forever; be honest instead.
    db.execute(
        """UPDATE research.research_runs
           SET status='failed', error_code='interrupted',
               error_message='The API restarted before this research run finished.',
               completed_at=now()
           WHERE status IN ('queued','running')"""
    )


def _json(v: Any) -> Any:
    if v is None or isinstance(v, (list, dict)):
        return v
    try:
        return json.loads(v)
    except (TypeError, ValueError):
        return None


_RUN_COLS = """r.id, r.objective, r.industry, r.geography, r.time_window, r.date_from, r.date_to,
    r.companies, r.source_preferences, r.status, r.provider, r.is_demo, r.provider_request_id,
    r.created_at, r.started_at, r.completed_at, r.error_code, r.error_message"""


def _run_row(row: dict[str, Any], with_result: bool) -> dict[str, Any]:
    row["companies"] = _json(row.get("companies")) or []
    row["source_preferences"] = _json(row.get("source_preferences")) or []
    if with_result:
        row["result"] = _json(row.get("result"))
    return row


def create_run(db: ApiDB, run: dict[str, Any]) -> None:
    db.execute(
        """INSERT INTO research.research_runs
           (id, objective, industry, geography, time_window, date_from, date_to, companies,
            source_preferences, status, provider, is_demo, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        [
            run["id"], run["objective"], run.get("industry"), run.get("geography"),
            run.get("time_window"), run.get("date_from"), run.get("date_to"),
            json.dumps(run.get("companies") or []), json.dumps(run.get("source_preferences") or []),
            run["status"], run["provider"], bool(run.get("is_demo")),
            run.get("created_at") or datetime.now(UTC),
        ],
    )


def set_status(db: ApiDB, run_id: str, status: str) -> None:
    db.execute(
        "UPDATE research.research_runs SET status=?, started_at=coalesce(started_at, now()) WHERE id=?",
        [status, run_id],
    )


def fail_run(db: ApiDB, run_id: str, code: str, message: str) -> None:
    db.execute(
        """UPDATE research.research_runs SET status='failed', error_code=?, error_message=?,
           completed_at=now() WHERE id=?""",
        [code, message[:1000], run_id],
    )


def complete_run(
    db: ApiDB,
    run_id: str,
    *,
    report: dict[str, Any],
    sources: list[dict[str, Any]],
    findings: list[dict[str, Any]],
    partial: bool,
    request_id: str | None,
    completed_at: datetime | None = None,
) -> None:
    db.execute("DELETE FROM research.research_sources WHERE research_run_id=?", [run_id])
    db.execute("DELETE FROM research.research_findings WHERE research_run_id=?", [run_id])
    for s in sources:
        db.execute(
            """INSERT INTO research.research_sources
               (id, research_run_id, url, domain, title, source_type, published_at, retrieved_at, snippet)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [s["id"], run_id, s["url"], s.get("domain"), s.get("title"), s.get("source_type"),
             s.get("published_at"), s.get("retrieved_at"), s.get("snippet")],
        )
    for f in findings:
        db.execute(
            """INSERT INTO research.research_findings
               (id, research_run_id, title, category, entity, industry, summary, significance,
                confidence, kind, event_date, source_ids, flags, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [f["id"], run_id, f["title"], f["category"], f.get("entity"), f.get("industry"),
             f.get("summary"), f.get("significance"), f.get("confidence"), f["kind"],
             f.get("event_date"), json.dumps(f.get("source_ids") or []),
             json.dumps(f.get("flags") or []), f.get("created_at") or datetime.now(UTC)],
        )
    db.execute(
        """UPDATE research.research_runs SET status=?, result=?, provider_request_id=?,
           completed_at=?, error_code=NULL, error_message=NULL WHERE id=?""",
        [
            "partial" if partial else "completed",
            json.dumps(report, default=str),
            request_id,
            completed_at or datetime.now(UTC),
            run_id,
        ],
    )


def _counts_join() -> str:
    return """LEFT JOIN (SELECT research_run_id, count(*) AS n FROM research.research_sources GROUP BY 1) s
                ON s.research_run_id = r.id
              LEFT JOIN (SELECT research_run_id, count(*) AS n FROM research.research_findings GROUP BY 1) f
                ON f.research_run_id = r.id"""


def list_runs(db: ApiDB, limit: int = 50) -> list[dict[str, Any]]:
    rows = db.query(
        f"""SELECT {_RUN_COLS}, coalesce(s.n,0) AS source_count, coalesce(f.n,0) AS finding_count
            FROM research.research_runs r {_counts_join()}
            ORDER BY r.created_at DESC LIMIT ?""",
        [limit],
    )
    return [_run_row(r, False) for r in rows]


def get_run(db: ApiDB, run_id: str) -> dict[str, Any] | None:
    row = db.query_one(
        f"""SELECT {_RUN_COLS}, r.result, coalesce(s.n,0) AS source_count, coalesce(f.n,0) AS finding_count
            FROM research.research_runs r {_counts_join()} WHERE r.id = ?""",
        [run_id],
    )
    return _run_row(row, True) if row else None


def list_sources(db: ApiDB, run_id: str) -> list[dict[str, Any]]:
    return db.query(
        """SELECT id, research_run_id, url, domain, title, source_type, published_at, retrieved_at, snippet
           FROM research.research_sources WHERE research_run_id=? ORDER BY source_type, domain""",
        [run_id],
    )


def _finding_row(r: dict[str, Any]) -> dict[str, Any]:
    r["source_ids"] = _json(r.get("source_ids")) or []
    r["flags"] = _json(r.get("flags")) or []
    return r


_FINDING_COLS = """f.id, f.research_run_id, f.title, f.category, f.entity, f.industry, f.summary,
    f.significance, f.confidence, f.kind, f.event_date, f.source_ids, f.flags, f.created_at"""


def list_findings(db: ApiDB, run_id: str) -> list[dict[str, Any]]:
    rows = db.query(
        f"""SELECT {_FINDING_COLS} FROM research.research_findings f
            WHERE research_run_id=? ORDER BY significance DESC NULLS LAST, title""",
        [run_id],
    )
    return [_finding_row(r) for r in rows]


def feed(
    db: ApiDB,
    *,
    category: str | None = None,
    kind: str | None = None,
    include_demo: bool = True,
    limit: int = 100,
    offset: int = 0,
) -> tuple[list[dict[str, Any]], int]:
    where = ["r.status IN ('completed','partial')"]
    params: list[Any] = []
    if category:
        where.append("f.category = ?")
        params.append(category)
    if kind:
        where.append("f.kind = ?")
        params.append(kind)
    if not include_demo:
        where.append("NOT coalesce(r.is_demo, false)")
    w = " AND ".join(where)
    base = f"FROM research.research_findings f JOIN research.research_runs r ON r.id = f.research_run_id WHERE {w}"
    total = db.scalar(f"SELECT count(*) {base}", params)
    rows = db.query(
        f"""SELECT {_FINDING_COLS}, r.objective AS run_objective, r.is_demo, r.provider
            {base} ORDER BY coalesce(r.completed_at, r.created_at) DESC, f.significance DESC NULLS LAST
            LIMIT ? OFFSET ?""",
        [*params, limit, offset],
    )
    return [_finding_row(r) for r in rows], int(total)


def category_counts(db: ApiDB) -> list[dict[str, Any]]:
    return db.query(
        """SELECT f.category, count(*) AS count FROM research.research_findings f
           JOIN research.research_runs r ON r.id=f.research_run_id
           WHERE r.status IN ('completed','partial') GROUP BY 1 ORDER BY 2 DESC"""
    )


def sources_by_ids(db: ApiDB, ids: list[str]) -> list[dict[str, Any]]:
    if not ids:
        return []
    ph = ",".join("?" for _ in ids)
    return db.query(
        f"SELECT id, url, domain, title, source_type FROM research.research_sources WHERE id IN ({ph})",
        ids,
    )
