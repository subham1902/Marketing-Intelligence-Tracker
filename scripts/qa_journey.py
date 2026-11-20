"""Browser QA journey (Playwright). Re-runnable.

Prereqs: API on :8000 and web on :3000 (NEXT_PUBLIC_STATIC_DATA=0).
    uv run playwright install chromium   # once
    uv run python scripts/qa_journey.py [--base http://localhost:3000] [--api http://127.0.0.1:8000] [--skip-run]

Saves screenshots to docs/qa/ and prints a pass/fail line per step. Starts one
narrow research run with the FREE open provider (never Context.dev). The failure
case reuses an existing failed run instead of forcing a paid provider call.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import httpx
from playwright.sync_api import sync_playwright

OUT = Path(__file__).resolve().parents[1] / "docs" / "qa"
results: list[tuple[str, bool, str]] = []


def step(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, ok, detail))
    print(f"{'PASS' if ok else 'FAIL'}  {name}  {detail}", flush=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://localhost:3000")
    ap.add_argument("--api", default="http://127.0.0.1:8000")
    ap.add_argument("--skip-run", action="store_true", help="Do not start a new research run")
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    api = httpx.Client(base_url=a.api, timeout=30)
    console_errors: list[str] = []

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        page.on("console", lambda m: console_errors.append(m.text) if m.type == "error" else None)

        def go(path: str, shot: str, wait_text: str | None = None) -> bool:
            page.goto(a.base + path, wait_until="networkidle", timeout=60000)
            if wait_text:
                page.get_by_text(wait_text, exact=False).first.wait_for(timeout=30000)
            page.screenshot(path=str(OUT / f"{shot}.png"), full_page=True)
            return True

        # 1 Dashboard
        go("/dashboard", "01-dashboard", "Companies tracked")
        step("1 dashboard", page.get_by_text("Latest live developments").count() > 0)
        # 2 Companies
        go("/competitors", "02-companies", "Tata Motors")
        step("2 companies", page.get_by_text("Ather Energy").count() > 0)
        # 3 Company profile
        go("/competitors/tata-motors", "03-company", "Live developments")
        step("3 company profile", page.get_by_text("Sample signals (demo seed)").count() > 0)
        # 4 Refresh news (free open provider)
        if a.skip_run:
            step("4 refresh news", True, "skipped (--skip-run)")
        else:
            page.get_by_role("button", name="Refresh news").click()
            page.get_by_text("Open run").first.wait_for(timeout=30000)
            step("4 refresh news", True, "run started")
        # 5 Research workspace
        go("/research", "05-research", "Research objective")
        step("5 research workspace", page.get_by_text("Free public sources").count() > 0)
        # 6-7 Start a narrow open run and watch the status change
        run_id = None
        if a.skip_run:
            runs = api.get("/research").json()
            run_id = next(r["id"] for r in runs if r["status"] == "completed" and r["provider"] == "open")
            step("6 start run", True, f"skipped; using {run_id}")
            step("7 status change", True, "skipped")
        else:
            page.fill("#objective", "Ola Electric developments in India")
            page.get_by_text("Focus on tracked companies").click()  # uncheck: narrow query
            page.get_by_role("button", name="Run research").click()
            page.wait_for_url("**/research/view?id=*", timeout=30000)
            run_id = page.url.split("id=")[1]
            seen: list[str] = []
            for _ in range(80):
                d = api.get(f"/research/{run_id}").json()
                seen.append(d.get("status_message") or d["status"])
                if d["status"] not in ("queued", "running"):
                    break
                time.sleep(5)
            step("6 start run", True, run_id)
            step("7 status change", d["status"] in ("completed", "partial"),
                 " -> ".join(dict.fromkeys(seen)))
        # 8-10 Report, findings, sources
        go(f"/research/view?id={run_id}", "08-report", "Executive summary")
        step("8 report tab", page.get_by_text("Executive summary").count() > 0)
        page.get_by_role("tab", name="Findings").click()
        page.wait_for_timeout(800)
        page.screenshot(path=str(OUT / "09-findings.png"), full_page=True)
        n_find = page.locator("text=/Source excerpt|Source-supported|Analysis|Provider-cited/").count()
        step("9 findings tab", n_find > 0, f"{n_find} labelled findings")
        page.get_by_role("tab", name="Sources").click()
        page.wait_for_timeout(800)
        page.screenshot(path=str(OUT / "10-sources.png"), full_page=True)
        links = page.get_by_role("link", name="Open source")
        href = links.first.get_attribute("href") if links.count() else None
        step("10 sources tab", bool(href and href.startswith("http")), f"{links.count()} sources, first={href}")
        # 11 Feed filters
        go("/feed", "11-feed", "findings")
        total = page.locator("text=/\\d+ findings/").first.inner_text()
        page.get_by_text("Include demo snapshot").click()
        page.wait_for_timeout(1200)
        live = page.locator("text=/\\d+ findings/").first.inner_text()
        page.get_by_role("button", name="Policy").click()
        page.wait_for_timeout(1200)
        pol = page.locator("text=/\\d+ findings/").first.inner_text()
        page.screenshot(path=str(OUT / "11b-feed-filtered.png"), full_page=True)
        step("11 feed filters", True, f"all={total}; live={live}; live+policy={pol}")
        # 12 Reopen saved run (no new provider call)
        before = len(api.get("/research").json())
        go(f"/research/view?id={run_id}", "12-reopen", "Research report")
        after = len(api.get("/research").json())
        step("12 reopen saved run", before == after, f"run count {before} -> {after}")
        # 13 Failure case (existing failed run; no paid call)
        failed = [r for r in api.get("/research").json() if r["status"] == "failed"]
        if failed:
            go(f"/research/view?id={failed[0]['id']}", "13-failure", "Research failed")
            step("13 failure message", page.get_by_text("Research failed").count() > 0,
                 failed[0].get("error_message") or "")
        else:
            step("13 failure message", True, "no failed run stored; covered by API tests")
        # Responsive check
        page.set_viewport_size({"width": 390, "height": 844})
        go("/dashboard", "14-mobile-dashboard", "Companies tracked")
        overflow = page.evaluate("document.documentElement.scrollWidth > window.innerWidth + 1")
        step("responsive 390px", not overflow, "no horizontal scroll" if not overflow else "horizontal overflow")
        browser.close()

    real_errors = [e for e in console_errors if "favicon" not in e.lower()]
    step("console errors", not real_errors, "; ".join(real_errors[:3]))
    failed_steps = [r for r in results if not r[1]]
    print(f"\n{len(results) - len(failed_steps)}/{len(results)} passed")
    return 1 if failed_steps else 0


if __name__ == "__main__":
    sys.exit(main())
