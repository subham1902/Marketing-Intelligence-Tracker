"""Export real (non-demo) research runs to a committed JSON fixture.

The DuckDB file is gitignored, so a fresh server (e.g. Emergent) would lose
the live research captured locally. ``seed_demo.py`` loads this fixture on
first boot, so hosted deployments start with real, source-linked reports.

Reads from the running API (no DuckDB lock):
    uv run python scripts/export_research_snapshot.py [--api http://127.0.0.1:8000] [run_id ...]
With no run ids, exports every completed non-demo run.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import httpx

OUT = Path(__file__).resolve().parents[1] / "config" / "research_snapshot.json"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--api", default="http://127.0.0.1:8000")
    ap.add_argument("run_ids", nargs="*")
    a = ap.parse_args()
    with httpx.Client(base_url=a.api, timeout=30) as c:
        runs = c.get("/research", params={"limit": 200}).json()
        wanted = set(a.run_ids)
        out = []
        for r in runs:
            if r["is_demo"] or r["status"] not in ("completed", "partial"):
                continue
            if wanted and r["id"] not in wanted:
                continue
            full = c.get(f"/research/{r['id']}").json()
            full["sources"] = c.get(f"/research/{r['id']}/sources").json()
            full["findings"] = c.get(f"/research/{r['id']}/findings").json()
            out.append(full)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"wrote {len(out)} runs -> {OUT}")


if __name__ == "__main__":
    main()
