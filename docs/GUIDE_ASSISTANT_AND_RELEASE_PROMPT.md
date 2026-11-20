# AUTONOMOUS TASK: Guide assistant, transparency layer, usability pass, public GitHub release

Work autonomously, make every routine decision yourself and do not stop to ask. Only stop for the two human-only cases in Phase E (GitHub not logged in, or a secret found and the safe fallback fails).

**Repo:** this `compete` folder. Branch: `hackathon/market-intelligence`.

**Read first:**
- `MORNING_REPORT.md`
- `PROGRESS.md`
- `IMPLEMENTATION_LOG.md`
- `docs/EMERGENT_HANDOFF.md`
- `CLAUDE.md`

The app is already working (77 tests, build green, new grid-map theme, Ctrl+K palette). **Do not redo or redesign existing work.**

## Rules (same as the overnight build)

- **Stack and dependencies:**
  - Keep the stack: Next.js 14, React 18, Tailwind 3, shadcn/Radix, framer-motion, TanStack Query, FastAPI, DuckDB.
  - No new database, state library, agent framework or paid service.
  - New npm/pip dependencies only if MIT/Apache, small, and compatible **without upgrading React, Next or Tailwind**. Check this with `npm view <pkg> peerDependencies license` before installing. Record each one in the log.
- **Free by default:** the guide must work with **no LLM and no key** (Emergent hosting has no local LLM). An LLM is optional polish only.
- **Never invent features:** the guide may only describe what exists in the code. Verify each answer against the actual routes and components.
- **Gates and commits:** after each phase, run `uv run pytest`, then `cd web && npx tsc --noEmit && npm run build`. Commit only when green: `guide: <what>`, `transparency: <what>`, `ux: <what>`, `release: <what>`.
- **When stuck:** if a step fails 3 times with different approaches, revert it, note it in the final report and move on.
- **Housekeeping:**
  - Keep `PROGRESS.md` updated per phase.
  - Windows/PowerShell; `$env:PYTHONUTF8=1`.
  - Stop the API before reseed or export.
  - Kill any servers you start.

---

## Phase A: Baseline (≤ 10 min)

1. Run `git status` and `git log --oneline -5`, then all three gates. Note the numbers in `PROGRESS.md`.
2. Inventory the real app: every route under `web/app`, the header/nav items, the Ctrl+K palette commands, the main buttons on each page, the API routers, and the provenance labels. Save it as `docs/APP_MAP.md`. It is the single source of truth for the guide's knowledge.

## Phase B: In-app guide assistant ("Ask the guide")

### Library decision (already researched; follow it)

**Build on the existing stack rather than adopting a full chat framework.**

| Option | Decision |
|---|---|
| **Streamdown** (`streamdown`, Vercel, open source) | **Use it for the message body.** It is a drop-in replacement for `react-markdown` (already used) with built-in per-word streaming animations (`animated` with `fadeIn` / `blurIn` / `slideUp`, plus `isAnimating`). That gives the ChatGPT-like motion.<br>It supports Tailwind v3 via a `content` glob entry `./node_modules/streamdown/dist/*.js`, plus `import "streamdown/styles.css"` for animations.<br>**Check its peerDependencies first.** If it needs React 19, try the latest version compatible with React 18. If none exists, fall back to `flowtoken` (`AnimatedMarkdown`). If that also fails, write a ~40-line framer-motion word-fade component over the existing `react-markdown`. Do not upgrade React. |
| **assistant-ui** (MIT) | Excellent ChatGPT-style UX, but it brings its own runtime and styling and may expect React 19 / Tailwind 4.<br>**Do not adopt it unless** `npm view @assistant-ui/react peerDependencies` is satisfied by React 18 / Tailwind 3 with no upgrades. Even then, prefer the custom widget below for weight and Emergent-friendliness. |
| **Vercel AI SDK `useChat`** | Not needed. The backend streams plain text, so read it with `fetch` + `ReadableStream`. One fewer dependency. |
| **react-chatbot-kit, chatscope, deep-chat** | Rejected: dated look, styling clashes, or a heavy web component. No streaming-motion advantage over the stack we already have. |

### Knowledge base

- Create `config/app_guide.yaml`, generated from `docs/APP_MAP.md`.
- Write about 30–50 entries covering:
  - **Navigation:** where things are.
  - **How-to:** run research, use templates, refresh company news, filter the feed, hide the demo snapshot, reopen saved runs, open sources, Ctrl+K.
  - **Concepts:** each provenance label (Source excerpt, Source-supported (quote verified), Provider-cited fact, Analysis, Demo snapshot, `[Sample]`); "why is a date Not available"; aggregator links; the GDELT window; free vs optional providers.
  - **Troubleshooting:** failed run, slow run, no results.
  - **About:** what the product does and what it does not do. Taken from the charter positioning and the known limitations, honestly.
- Fields per entry: `id`, `title`, `keywords`, `answer` (markdown, 2–6 sentences), `route` (optional), `action_label` (optional), `related` (ids).
- Every claim must match the real UI.

### Backend

`POST /assistant/chat` (plus the `/api` mirror, following the existing pattern).

**Request:**
```
{ message, pathname, history?: [...last 6], activity?: [...last 10 activity entries] }
```

**Response:** streamed `text/plain` (FastAPI `StreamingResponse`), with a final JSON trailer line `\n\n<<META>>{...}` carrying `{ actions: [{label, route}], suggestions: [3 follow-ups], sources: [entry ids] }`. The frontend strips the trailer before rendering.

#### Answering logic (`pipeline/assistant/guide.py`, pure functions)

1. **Retrieval:** pure-Python BM25 over title + keywords + answer, plus a boost for entries whose `route` matches `pathname`.
2. **Live-status intents** (real data from DuckDB, never invented):
   - "what's running / status of my research / latest run" → most recent runs with status/stage and a link.
   - "what's in the feed today" → counts by category.
   - "how many companies" → the real count.
3. **"What just happened?"** → summarize the `activity` entries the client sent, in plain words.
4. **Low confidence** → say so honestly. Offer the 3 closest topics as suggestions; never make up features.
5. **Optional LLM rephrase:** only if `COMPETE_LLM_PROVIDER=ollama` and it is reachable within 2 s. Give the model only the retrieved entries and require it to stay within them. If it times out or errors, fall back to the deterministic answer. **The deterministic path is the default and must be excellent on its own.**
6. **Streaming:** stream the deterministic answer in word chunks, about 25–40 ms apart, so the motion feels natural. Stream LLM tokens as they arrive.

**Tests (pytest, no network):** retrieval picks the right entry for 10 sample questions; pathname boost works; the status intent reads DuckDB; low-confidence fallback; the trailer parses; the route streams.

### Frontend (`web/components/guide/*`)

- **Launcher:** floating bottom-right, in the existing theme (teal/saffron). It springs in with framer-motion, shows a subtle pulse the first time, and remembers it was opened before (`localStorage`, try/catch).
- **Panel:**
  - Radix Dialog/Popover for focus trap, Esc to close and an `aria-modal` label.
  - Spring open/close animation. About 380×560 on desktop; a full-height sheet at ≤ 640 px width.
  - **Header:** "Guide", with a context line such as "You're on Research".
  - **Message list:** user and assistant bubbles; auto-scroll that pauses if the user scrolls up.
  - A three-dot typing indicator until the first chunk arrives, then **Streamdown with the animated word reveal**, plus a caret while streaming.
- **Content features:**
  - **Action buttons** from META navigate with the Next router and close the panel on mobile.
  - **Suggestion chips** appear after each answer.
  - **Starter chips** depend on the current page. For example, on Research: "How do I run research?", "What does Source excerpt mean?", "Why is my run slow?".
- **Controls:**
  - Stop button while streaming (`AbortController`).
  - Copy answer.
  - "New chat".
  - History kept in `sessionStorage` (try/catch).
- **Integration:** add "Ask the guide…" to the Ctrl+K palette (it opens the panel prefilled), and a global shortcut `Ctrl+/` (show it in the palette).
- **Accessibility and motion:** respect `prefers-reduced-motion` (no word animation, instant text). Use `aria-live="polite"` on the streaming region.
- **Static mode:** if the backend is unreachable, show a clear "Guide needs the API running" state with a retry.

## Phase C: Transparency layer (subtle, always-on)

The goal: **after every click the user can see what the system is doing, what happened, and where it went.** Keep it understated; it should not become noisy.

### 1. Global activity bar

- A 2 px bar at the very top of the viewport, in the theme accent.
- It animates while either is true:
  - Any TanStack Query fetch or mutation is in flight (`useIsFetching()` / `useIsMutating()`, already available).
  - A route transition is in progress (detect `pathname` / `searchParams` change in a client component).
- Its width is eased with framer-motion and it fades out on completion.
- **No new dependency.** Only if this proves unreliable, use `nextjs-toploader` (verify MIT and React 18 peer compatibility first).

### 2. Reading progress bar

- On long pages (research report/view, findings and sources tabs, company profile, docs-like pages), show a thin bar under the header driven by `useScroll` (framer-motion).
- Hide it when the page doesn't scroll.

### 3. Activity tracker

**Store:** `web/lib/activity.ts`, a React context plus a reducer (no new state library). It keeps the last 100 entries, persisted to `localStorage` (try/catch).

**What to log** (instrument once, centrally):

- **API calls:** wrap the existing API client/fetcher so every request logs:
  - a human label from a map (e.g. `POST /research` → "Started a research run"; `POST /companies/{id}/refresh` → "Refreshing news for Tata Motors"; `GET /findings` → "Loaded intelligence feed")
  - the status (pending → success/error)
  - the duration
  - a short error reason
  - Never log keys or full payloads.
- **Navigation:** "Opened Companies → Ola Electric".
- **Key user actions:** Run research, template used, Refresh news, feed filter changed, demo toggle, open source (external), copy, palette command.
- **Research run stage changes** observed while polling (Discovering → Fetching 25 sources → Synthesizing → Completed/Failed). Each entry links to the run.

**UI:**

- A small "Activity" button in the header (lucide icon) with:
  - a pulsing dot while anything is running
  - a count badge for unseen failures
- It opens a right-side drawer with a timeline grouped as "Now / Earlier today". Each row shows: icon by type, label, relative time, duration, status colour, and a link to the relevant page.
- Filters: All / Running / Errors. A "Clear" button.
- **Toasts:** use the existing `sonner`, only for completions and failures of long tasks (research runs, refresh), never for every click.

**Feed the guide:** send the last 10 activity entries with each guide message, so it can answer "what just happened?" and "why did that fail?".

**Tests:** if a frontend test runner already exists, add tests. If not, keep the logic in pure functions (the label map, the reducer) and cover them through tsc; do not add a test framework tonight.

## Phase D: Full usability check, and fix what you find

Start the API (8000) and web (3000). Use the built-in browser, as in the overnight QA. A local hook blocks Playwright from the shell; still try `scripts/qa_journey.py` once, and record the result.

**Walk the whole journey, including the new features:**
1. Dashboard
2. Companies → profile → Refresh news (watch the activity bar, drawer entries and the completion toast)
3. Research: template run, then watch the stages and activity
4. Report, Findings and Sources tabs (reading bar)
5. Open a source
6. Feed filters and the demo toggle
7. Reopen a saved run
8. A failure case
9. Ctrl+K
10. Guide:
    - ask 10 varied questions, including "where do I run research?", "what does Source excerpt mean?", "what just happened?", "status of my research", and an off-topic question
    - use the action buttons and suggestion chips, Stop, and reduced motion

**Check each screen against this list:**
- Clear primary action
- Loading, empty and error states
- Labels in plain words
- Keyboard-only navigation (Tab, Enter, Esc)
- Visible focus
- Contrast is readable in the theme
- Nothing overlaps (the guide launcher vs page buttons and toasts)
- 1280 px and 390 px widths
- No console errors
- No dead links
- Any action over 1 s shows feedback

**Fix** every issue that can be fixed in under about 20 minutes. Write `docs/USABILITY_REPORT.md` as a table: issue, where, severity, fixed? (yes/no + commit). Save screenshots to `docs/qa/` (desktop and mobile; guide open; activity drawer open).

## Phase E: Publish to GitHub (public)

### E1. Pre-flight

- All gates green and a clean working tree.
- Update `README.md`:
  - a one-paragraph pitch
  - 3–4 screenshots from `docs/qa/`
  - "Quick start (free, no keys)"
  - optional providers
  - the Emergent hosting section
  - **attribution:** "Built on [yassnemo/compete](https://github.com/yassnemo/compete) (MIT)"
  - Keep `LICENSE` unchanged.

### E2. Secret scan (mandatory; full history)

1. **Known values:** in a small Python script, read every non-empty value from `.env` whose name contains `KEY`, `TOKEN` or `SECRET` (e.g. `CONTEXT_DEV_API_KEY`). Search `git log --all -p` for each value and **print only the variable name and the match count, never the value**.
2. **Pattern scan** across history: `sk-`, `AIza`, `gsk_`, `ghp_`, `github_pat_`, `xox[bp]-`, `-----BEGIN .*PRIVATE KEY-----`, plus long high-entropy strings assigned to `*key*` / `*token*` / `*secret*`.
3. **Tracked files:** `git ls-files` must not include `.env`, `.env.local`, anything under `data/`, `*.duckdb` or `*.parquet` (other than intentionally committed fixtures such as `config/research_snapshot.json`), and no file over 50 MB.

**If anything is found in history:** do **not** rewrite the local history.
- Create an orphan branch `release-main` from the current clean tree, in one commit: "Market Intelligence Tracker: hackathon release (built on yassnemo/compete, MIT)".
- Re-run the scan on that branch and push **only that branch** as `main`.
- If the scan still finds something, stop and report (a human case).

### E3. Remotes

1. `git remote -v`. The current `origin` is very likely `yassnemo/compete`: rename it to `upstream` (`git remote rename origin upstream`). **Never push to upstream.**
2. Run `gh auth status`. If it isn't logged in or isn't installed: **stop here** and put the exact commands for the user in the report (`winget install GitHub.cli`, `gh auth login --web`, then "re-run Phase E").

### E4. Create and push

1. `gh repo create market-intelligence-tracker --public --source . --remote origin --description "India-first market & competitive intelligence workspace: free public-source research, evidence-linked findings, company tracking (hackathon MVP)"`
   - If the name is already taken on the account, use `market-intelligence-tracker-hackathon`.
2. Push: `git push -u origin hackathon/market-intelligence:main` (or `release-main:main` if E2 required it). Also push the working branch name for history if it was scan-clean.
3. Add topics with `gh repo edit --add-topic`: `market-intelligence`, `competitive-intelligence`, `fastapi`, `nextjs`, `duckdb`, `india`, `hackathon`.

### E5. Verify on GitHub

- `gh repo view --json url,visibility,defaultBranchRef` shows PUBLIC, branch `main`.
- `gh api repos/{owner}/{repo}/contents/.env` must return 404.
- The README renders and its screenshot links resolve.

## Final report

Write `RELEASE_REPORT.md` in the repo root, commit it and push it. Keep it to 1 page:
- **Repo URL**
- **What was added:** guide, activity bar, reading bar, activity tracker, usability fixes
- **Library decisions:** which package was used and why; any fallback taken
- **Gates:** actual numbers
- **Usability findings:** fixed vs open
- **Secret-scan result:** counts only
- **Manual steps:** only if truly required, e.g. `gh auth login`, "rotate the Context.dev key (it was pasted in chat earlier; rotate even though it's not in the repo)", "connect Emergent to the GitHub repo"
- **How to demo the guide and activity tracker in 60 seconds**

Begin with Phase A now. Do not ask for confirmation.
