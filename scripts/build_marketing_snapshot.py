"""Precompute Marketing Analyses for the tracked companies into config/marketing_snapshot.json.

Runs the pipeline directly (no API, no DuckDB lock):
    PYTHONUTF8=1 uv run python scripts/build_marketing_snapshot.py [company-id ...]
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from pipeline.config import Settings  # noqa: E402
from pipeline.marketing import service  # noqa: E402
from pipeline.research.open_provider import OpenConfig, OpenResearchProvider  # noqa: E402
from seed_demo import COMPETITORS  # noqa: E402

OUT = ROOT / "config" / "marketing_snapshot.json"


def main(only: list[str]) -> None:
    tracked = [{"id": c[0], "name": c[1], "industry": c[3]} for c in COMPETITORS]
    rivals = service.build_rivals(tracked)
    existing = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {"analyses": []}
    keep = [a for a in existing["analyses"] if only and a["company"] not in only]
    prov = OpenResearchProvider(OpenConfig(cache_dir=Settings().data_dir / "research_cache", throttle_seconds=0.5))
    out = list(keep)
    for c in tracked:
        if only and c["id"] not in only:
            continue
        company = service.build_company(c["id"], c["name"], c["industry"])
        result, mode, items = service.run(prov, company, rivals, status_cb=lambda s, n=c["name"]: print(n, s))
        now = datetime.now(UTC).isoformat()
        out.append({"id": f"mk-snap-{c['id']}", "company": c["id"], "company_name": c["name"], "mode": mode,
                    "created_at": now, "completed_at": now, "result": result, "evidence": items})
        print(c["name"], "->", len(items), "sources", mode, flush=True)
        OUT.write_text(json.dumps({"captured_at": now, "analyses": out}, indent=1, default=str), encoding="utf-8")
    prov.close()


if __name__ == "__main__":
    main(sys.argv[1:])
