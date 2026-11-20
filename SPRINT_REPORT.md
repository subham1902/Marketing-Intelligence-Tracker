# Sprint report: Marketing Analysis and judging improvements (20 Nov 2026, 13:03–14:50 IST)

## What shipped (pushed to `origin/main`: `6a9a9ee`, `902f071`, `57ab213`, plus this report)

- **Marketing Analysis module**
  - Location: `/marketing`, a sidebar item, Ctrl+K "Marketing analysis: <company>", a button on each company profile, and 3 guide entries.
  - Content: 13 evidence-linked sections. Snapshot with a coverage meter, Profitability, Moat, Stakeholder 2×2, Porter radar, Competition, Tone gauge and trend, Need gaps, Segmentation, Positioning (timeline and map), Go-to-market, 7P scorecard, and prioritised to-do cards.
  - Every claim has an evidence chip that opens the quote and the source, or a label: Analysis, AI analysis, Forecast or Not found. Each section has a "How this was scored" note.
- **Pipeline:** `pipeline/marketing/`
  - Free evidence gathering: 15 queries, up to 30 sources.
  - Deterministic extraction. Figures come only from fetched page text and never from headlines.
  - Rule-based synthesis, plus an optional AI pass that rejects any number not in the cited evidence and marks quotes it cannot match as "not quote-verified".
- **API and storage:**
  - `POST/GET /marketing/analyses`, also served under `/api`, stored in `research.marketing_analyses`.
  - `/api/health` now reports version, LLM mode and snapshot counts.
- **Captured snapshot:** `config/marketing_snapshot.json`
  - All 7 tracked companies, 30 real sources each, AI-assisted using local `qwen2.5:7b`. Every AI claim passed the number check.
  - Reloaded on every boot, so a judge sees a full deck instantly with no live calls.
- **Other additions:**
  - "Compare with" head-to-head table (Five Forces, Moat, 7P, tone).
  - Copy share link, and Download PDF through an A4 print stylesheet.
  - Live "Analyse any company" runs, with stages logged to the Activity drawer and a completion toast.
  - Groq hint in the Connect LLM panel.
- **Docs:** `docs/PITCH.md` (one-liner, 90-second story, 3-minute demo script, honest gaps, 15-question Q&A crib sheet), `docs/DEPLOY_CHECKLIST.md`, `docs/JUDGE_SCORECARD.md`.

## Gates (actual)

| Gate | Result |
|---|---|
| pytest | 101 passed, up from 94; 7 new marketing tests, no network |
| tsc | Clean |
| lint | Clean |
| next build | Compiled; `/marketing` is 12.9 kB |
| Secret scan | 0 known `.env` values. 3 pattern hits, all the pattern names written out in existing docs (`github_pat_`, `ctxt_secret`) |

## Browser checks

- Ather and Tata decks load.
- The Porter section and an evidence-chip popover work.
- At 390 px there is no horizontal scroll, and the section chips scroll sideways.
- A live Bajaj Auto run completed: 30 sources, 24 read in full.
- Compare Ather vs Ola renders.
- The guide answers "Porter for Ather" with a working action button.
- **Not re-checked after the final commit:** the print preview and the AI badge in the UI. The API restart that loads the AI snapshot is untested.

## Rubric (before → now)

| Criterion | Before | Now |
|---|---|---|
| Working product | 4 | 4 (8 or more once deployed) |
| Creativity | 3 | 4 |
| Build quality & AI | 3 | 3.5 |
| Idea clarity | 2 | 2.5 |
| Pitch & Q&A | ? | 3 |

Evidence for each score is in `docs/JUDGE_SCORECARD.md`.

## Known gaps

- Ratings come from keyword rules, so they are crude when coverage is thin.
- Stakeholder placement uses default positions per stakeholder type.
- The battle-card export and the animated reveal were not built.
- There is no static-export mode for `/marketing`; it needs the live backend.
- Live runs on a cloud IP may be rate-limited. The captured analysis is the fallback.
- The hook's `agents/context.md` file does not exist.

## Human steps left

1. Deploy on Emergent following `docs/DEPLOY_CHECKLIST.md`, then run its 2-minute smoke test.
2. Optional: add a free Groq key through **Connect LLM** so live runs on the host are AI-assisted.
3. Rotate the Context.dev key. It was never committed, but rotate it anyway.
4. Fill in "Mentor feedback we acted on" in `docs/PITCH.md`.
