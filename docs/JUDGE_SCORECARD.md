# Judge scorecard (honest self-score)

Updated 20 Nov 2026 during the judging sprint. "Before" is the start of the sprint (13:03 IST).

| Criterion | Pts | Before | Now | Evidence | What would move it |
|---|---|---|---|---|---|
| Working product | 9 | 4 | 4 (8 once deployed) | Main flow works end to end locally. Marketing Analysis opens instantly from `config/marketing_snapshot.json` (7 companies, real sources). A live "Analyse any company" run was verified in the browser (Bajaj Auto: 30 sources, 24 read). `/api/health` reports the snapshot counts. | **Deploy on Emergent** per `docs/DEPLOY_CHECKLIST.md`. Localhost-only is capped at 4. |
| Creativity & fun | 5 | 3 | 4 | A 13-section consultant deck with radar, positioning map, stakeholder 2×2, 7P scorecard and to-do cards. It has a share link and A4 PDF export, and analyses any company by name. | Compare two companies; a battle-card export |
| Build quality & AI use | 4 | 3 | 3.5 | Real scraping plus deterministic extraction. The AI mode is validated: invented numbers are rejected and quotes are verified. There are 101 tests with no network calls. Clean at 390 px, with no horizontal scroll. | Turn on a free Groq key on the host so the "AI-assisted · N quote-verified" badge shows live |
| Idea clarity | 3 | 2 | 2.5 | One-liner and 90-second story in `docs/PITCH.md` | Fill in "Mentor feedback we acted on" |
| Pitch & Q&A | 4 | ? | 3 | A 3-minute demo script mapped to the rubric, an honest-gaps slide and a 15-question crib sheet | Rehearse once as a team |
