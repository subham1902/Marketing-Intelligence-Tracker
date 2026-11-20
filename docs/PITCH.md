# Pitch kit

## One line

**India's SMEs get consultant-grade, evidence-linked market intelligence on any competitor, free.**

## 90-second story

A marketing head at a mid-size Indian company wants to know what Ather or Tata Motors is doing. Today they have two choices: pay a consultant for a deck that arrives weeks later, or spend days on Google with no structure.

Market Intelligence Tracker reads free public sources: news, Google News, government press releases and company pages. It turns them into the frameworks a consultant would use: moat, Porter's Five Forces, stakeholders, positioning, go-to-market, the 7P marketing mix and a prioritised to-do list.

The difference is honesty. Every claim carries a chip. Click it and you see the exact sentence and a link to the source. Anything that is our inference is labelled *Analysis*, and projections are labelled *Forecast*. A revenue figure only appears if a source sentence contains that figure; otherwise we say "Not found in public sources".

It costs nothing to run. There are no paid APIs and no LLM is required. If you add a free Groq key, an AI layer writes extra insights, and each one is checked against the cited quote.

## 3-minute demo script (one rubric line per beat)

| Time | Beat | Rubric |
|---|---|---|
| 0:00 | Open the live URL → Overview is filled with real developments | Working product |
| 0:20 | Sidebar → **Marketing Analysis** → Ather Energy: the full deck renders instantly | Working product, Creativity |
| 0:45 | Scroll the rail: Snapshot coverage → Moat bars → Five-forces radar → positioning map | Creativity |
| 1:15 | Click an evidence chip: quote + **Open source**. Open *How this was scored* | Build quality & AI, Honesty |
| 1:35 | Profitability: real ₹ crore figures with quotes; show a "Not found" label elsewhere | Honesty |
| 1:50 | To-do cards: each one names the finding that triggered it, plus impact, effort and KPI | Idea clarity |
| 2:05 | Type "Bajaj Auto" → **Analyse**: live stages in the Activity drawer, completion toast | AI/APIs doing real work |
| 2:30 | **Copy share link** and **Download PDF** (A4) | Creativity (shareable) |
| 2:45 | Phone view (390 px) plus the guide bot answering "Porter for Ather?" | Build quality |
| 2:55 | Close on the one-liner | Idea clarity |

## Honest gaps (one slide)

- Free sources can be rate-limited or blocked from cloud IPs. Captured analyses are the fallback, and each one is labelled with its capture date.
- Rule-based ratings come from keyword rules. They are transparent and explainable, but cruder than an analyst. We label them *Analysis*.
- Tone is a lexicon score over news text. It is **not** customer sentiment.
- Stakeholder power/interest uses standard defaults per stakeholder type. Only the evidence is company-specific.
- No authentication or multi-user workspaces yet.

## Q&A crib sheet

1. **Where does the data come from?** DuckDuckGo news, Google News RSS, PIB press releases and the pages themselves (fetched and parsed with trafilatura). No paid APIs.
2. **How do I know a claim is real?** Every evidence chip opens the exact sentence and its source URL. Figures are taken only from fetched page text, never from headlines.
3. **Does it hallucinate?** Without a key there is no LLM at all, so it can't. With a key, AI claims must cite evidence ids. Any claim containing a number that isn't in the cited source is rejected, and quotes that can't be matched are marked "not quote-verified".
4. **What does it cost?** ₹0. It runs on free sources. AI is optional, through a free Groq tier or local Ollama.
5. **How are Five Forces scored?** By transparent rules. For example, rivalry is high if 4 or more rivals are co-mentioned. Every section has a "How this was scored" panel.
6. **Why rule-based and not just GPT?** It's reproducible, auditable and free. The AI is an optional layer on top, not the foundation.
7. **How fast is it?** Captured analyses open instantly. A live run on a new company takes roughly 30–90 seconds, depending on the sources.
8. **Can I analyse any company?** Yes. Type a name, and it becomes a temporary entity using the same pipeline.
9. **Architecture?** Next.js 14 frontend, FastAPI backend, DuckDB storage. The pipeline runs gather → deterministic signal extraction → framework synthesis, with an optional validated AI pass.
10. **What if sources are blocked on the server?** The run finishes with whatever it found, or fails readably. The latest captured analysis stays one click away.
11. **Who is it for?** SME marketing and strategy teams, founders, consultants and students in India.
12. **What's the moat?** Evidence-linking plus India-specific sources (PIB, Indian news) and the framework layer. Generic chatbots don't cite at sentence level.
13. **Roadmap?** Scheduled re-runs with change alerts, side-by-side company comparison, a battle-card export, more Indian sources (MCA filings, BSE announcements) and team workspaces.
14. **How is it tested?** Over 100 automated tests run with no network: figure extraction, every Porter rule, the AI fallback and the invented-number rejection.
15. **Biggest limitation?** Keyword rules can mis-rate a dimension when coverage is thin. The coverage meter in the Snapshot shows when to trust a section less.

## Mentor feedback we acted on

_To be filled in by the team. Do not invent this._

-
