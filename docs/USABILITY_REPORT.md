# Usability report: 20 Nov 2026

Method: a click-through in the built-in browser with the API on :8000 and the web app on :3000.

`scripts/qa_journey.py` was tried once. It needs `playwright install` (a Chromium download), which a local hook blocks, so the journey was walked manually instead. Screenshots are in `docs/qa/`.

## Journey covered

1. Dashboard.
2. Companies → TVS Motor → **Refresh news**. The stage bar animated, the activity drawer showed live stages, and the run completed with 19 findings.
3. Research workspace with templates.
4. Report, Findings and Sources tabs.
5. Open source.
6. Feed filters and the demo toggle.
7. Reopening a saved run.
8. A failed run (`missing_key`).
9. Ctrl+K.
10. The guide. I asked 10 questions; the results are below.

## Guide answers (10 questions)

| Question | Result |
|---|---|
| where do I run research? | Correct: Research page and Ctrl+K, with an *Open Research* action |
| what does Source excerpt mean? | Correct label explanation |
| what just happened? | Read the activity log: "Your last action that failed: Started a research run (500)" |
| what's the status of my research? | Live from DuckDB: latest runs with status, counts and *Open latest run* |
| weather in Mumbai? (off-topic) | Said it isn't sure and offered 3 close topics; nothing invented |
| how many companies? | "7 companies" (live count) |
| what's in the feed today? | Live total and the top categories |
| why is the date not available? | Correct ("the app never guesses a date") |
| how do I connect groq? | Correct Connect LLM steps |
| does it work without AI? | Correct (extractive, cited) |

Also checked:
- Streaming word reveal, then action buttons, copy, suggestion chips and **Stop**.
- Ctrl+/ opens the guide; Esc closes it.
- Starter chips match the current page.

## Issues

| # | Issue | Where | Severity | Fixed? |
|---|---|---|---|---|
| 1 | Hydration error on every page: the activity bar rendered differently on the server and the client | Global | High | Yes: client-only after mount (guide commit) |
| 2 | Past stage entries kept a spinning icon in the Activity drawer, suggesting they were still running | Activity drawer | Medium | Yes: static icon for finished stages |
| 3 | "Tvs Motor" capitalisation in activity labels | Activity labels | Low | Yes: acronym-aware names |
| 4 | Guide launcher covered content at 390 px | Mobile, all pages | Medium | Yes: icon-only launcher on small screens |
| 5 | Toasts would stack under the guide launcher (bottom-right) | Global | Medium | Yes: toasts moved to bottom-left |
| 6 | "Research submitted" and "Refreshing news" toasts fired on every click (noisy) | Research, Companies | Low | Yes: replaced by the stage bar and the Activity drawer, with completion and failure toasts only |
| 7 | Navigation entries are not logged on a full page reload (only on in-app navigation) | Activity tracker | Low | No (by design: a reload isn't a user navigation step) |
| 8 | The automation's key event for Ctrl+/ didn't fire, so the shortcut was verified with a dispatched key event | Guide shortcut | Info | n/a |
| 9 | Scripted QA can't run on this machine (hook blocks the browser download) | QA | Info | No: manual walk-through used |

## Checklist

| Check | Result |
|---|---|
| Clear primary action on each page | Yes: Run research, Refresh news, Connect LLM, Ask the guide |
| Loading, empty and error states | Yes, via AsyncState skeletons, empty states and red failure boxes |
| Keyboard | Tab and Enter work in the forms and palette; Esc closes the palette, LLM panel, Activity drawer and guide. The guide uses a Radix Dialog with a focus trap |
| Visible focus | Focus rings on inputs, buttons and textareas |
| Readable contrast | Yes, in light and dark themes |
| Nothing overlaps | Yes, at 1280 px and 390 px after fixes 4–5 |
| No horizontal scroll at 390 px | Yes (`scrollWidth == innerWidth`) |
| No console errors | Yes after fix 1 |
| Feedback for actions over 1 s | Activity bar, stage bar, guide typing dots, and spinners on buttons |
