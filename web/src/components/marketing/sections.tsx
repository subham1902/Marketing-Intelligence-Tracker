"use client";

import { motion, useReducedMotion } from "framer-motion";
import { ChevronDown, ExternalLink, Flame, Gauge as GaugeIcon, Shield, Sparkles, Target } from "lucide-react";
import { createContext, useContext, useState, type ReactNode } from "react";

import { cn } from "@/lib/utils";
import type { Ev, EvidenceItem, MarketingResult } from "@/lib/marketing-api";

export const EvidenceCtx = createContext<Map<string, EvidenceItem>>(new Map());

const LABEL_STYLE: Record<string, string> = {
  Evidence: "bg-emerald-500/15 text-emerald-700 dark:text-emerald-300",
  Analysis: "bg-sky-500/15 text-sky-700 dark:text-sky-300",
  "AI analysis": "bg-violet-500/15 text-violet-700 dark:text-violet-300",
  "AI analysis (not quote-verified)": "bg-amber-500/15 text-amber-700 dark:text-amber-300",
  Forecast: "bg-fuchsia-500/15 text-fuchsia-700 dark:text-fuchsia-300",
  "Not found": "bg-muted text-muted-foreground",
  "Rule-based recommendation": "bg-sky-500/15 text-sky-700 dark:text-sky-300",
  "AI recommendation": "bg-violet-500/15 text-violet-700 dark:text-violet-300",
};

export function Label({ children }: { children: string }) {
  return (
    <span className={cn("inline-block rounded px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide", LABEL_STYLE[children] ?? LABEL_STYLE.Analysis)}>
      {children}
    </span>
  );
}

const RATING: Record<string, string> = {
  strong: "bg-emerald-500", high: "bg-rose-500", moderate: "bg-amber-500", medium: "bg-amber-500",
  average: "bg-amber-500", weak: "bg-rose-400", low: "bg-emerald-500", unknown: "bg-muted-foreground/30",
};
const WIDTH: Record<string, number> = { strong: 100, high: 100, moderate: 60, medium: 60, average: 60, weak: 30, low: 30, unknown: 6 };

export function Chip({ ev }: { ev: Ev }) {
  const map = useContext(EvidenceCtx);
  const [open, setOpen] = useState(false);
  const src = map.get(ev.evidence_id);
  return (
    <span className="relative inline-block">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="mr-1 mt-1 inline-flex max-w-[16rem] items-center gap-1 truncate rounded-full border bg-background px-2 py-0.5 text-[11px] text-muted-foreground hover:text-foreground print:hidden"
        aria-expanded={open}
      >
        {src?.domain ?? "source"}
        {src?.date ? ` · ${src.date}` : ""}
      </button>
      {open && (
        <span className="absolute left-0 z-30 mt-1 block w-[min(20rem,80vw)] rounded-lg border bg-popover p-3 text-xs shadow-lg">
          <span className="block italic">“{ev.quote}”</span>
          {src?.aggregator && <span className="mt-1 block text-muted-foreground">Headline via news aggregator.</span>}
          {src && (
            <a href={src.url} target="_blank" rel="noreferrer" className="mt-2 inline-flex items-center gap-1 text-primary hover:underline">
              Open source <ExternalLink className="h-3 w-3" />
            </a>
          )}
        </span>
      )}
      <span className="hidden text-[10px] text-muted-foreground print:inline">[{src?.domain}] </span>
    </span>
  );
}

export function Chips({ ev }: { ev?: Ev[] }) {
  if (!ev?.length) return null;
  return <div className="flex flex-wrap">{ev.map((e, i) => <Chip key={i} ev={e} />)}</div>;
}

export function Section({ id, title, children, how }: { id: string; title: string; children: ReactNode; how?: string }) {
  const [open, setOpen] = useState(false);
  const reduce = useReducedMotion();
  return (
    <motion.section
      id={id}
      initial={reduce ? false : { opacity: 0, y: 18 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-60px" }}
      transition={{ duration: 0.45, ease: "easeOut" }}
      className="mk-section glass scroll-mt-24 rounded-2xl border p-4 sm:p-5 print:break-inside-avoid"
    >
      <h2 className="mb-3 text-base font-semibold tracking-tight">{title}</h2>
      {children}
      {how && (
        <div className="mt-3 border-t pt-2 text-xs text-muted-foreground print:hidden">
          <button type="button" onClick={() => setOpen((o) => !o)} className="inline-flex items-center gap-1 hover:text-foreground">
            How this was scored <ChevronDown className={cn("h-3 w-3 transition", open && "rotate-180")} />
          </button>
          {open && <p className="mt-1">{how}</p>}
        </div>
      )}
    </motion.section>
  );
}

function Bar({ rating }: { rating: string }) {
  return (
    <div className="h-2 w-full overflow-hidden rounded-full bg-muted">
      <div className={cn("h-full rounded-full", RATING[rating] ?? RATING.unknown)} style={{ width: `${WIDTH[rating] ?? 6}%` }} />
    </div>
  );
}

function RatedRow({ name, rating, ev, label }: { name: string; rating: string; ev: Ev[]; label: string }) {
  return (
    <div className="py-2">
      <div className="mb-1 flex items-center justify-between gap-2 text-sm">
        <span className="font-medium">{name}</span>
        <span className="flex items-center gap-2">
          <span className="text-xs capitalize text-muted-foreground">{rating}</span>
          <Label>{label}</Label>
        </span>
      </div>
      <Bar rating={rating} />
      <Chips ev={ev} />
    </div>
  );
}

const LEVEL_N: Record<string, number> = { low: 1, medium: 2, high: 3 };

function Radar({ data }: { data: { force: string; level: string }[] }) {
  const R = 80, cx = 110, cy = 100;
  const pt = (i: number, r: number) => {
    const a = (Math.PI * 2 * i) / data.length - Math.PI / 2;
    return [cx + r * Math.cos(a), cy + r * Math.sin(a)];
  };
  const poly = data.map((d, i) => pt(i, (R * (LEVEL_N[d.level] ?? 0)) / 3).join(",")).join(" ");
  return (
    <svg viewBox="-30 -5 280 215" className="mx-auto h-52 w-full max-w-xs" role="img" aria-label="Porter five forces radar">
      {[1, 2, 3].map((l) => (
        <polygon key={l} points={data.map((_, i) => pt(i, (R * l) / 3).join(",")).join(" ")} className="fill-none stroke-border" />
      ))}
      <polygon points={poly} className="fill-primary/25 stroke-primary" strokeWidth={2} />
      {data.map((d, i) => {
        const [x, y] = pt(i, R + 14);
        return (
          <text key={d.force} x={x} y={y} textAnchor="middle" className="fill-muted-foreground text-[8px]">
            {d.force.replace("Threat of ", "")}
          </text>
        );
      })}
    </svg>
  );
}

function Gauge({ score }: { score: number }) {
  const a = Math.PI * (1 - (score + 1) / 2);
  const x = 60 + 45 * Math.cos(a), y = 60 - 45 * Math.sin(a);
  return (
    <svg viewBox="0 0 120 70" className="h-24 w-40" role="img" aria-label={`Tone ${score.toFixed(2)}`}>
      <path d="M15 60 A45 45 0 0 1 105 60" className="fill-none stroke-muted" strokeWidth={10} />
      <path d="M15 60 A45 45 0 0 1 105 60" className="fill-none stroke-primary/40" strokeWidth={10} strokeDasharray="4 3" />
      <line x1={60} y1={60} x2={x} y2={y} className="stroke-foreground" strokeWidth={3} strokeLinecap="round" />
      <text x={60} y={68} textAnchor="middle" className="fill-foreground text-[10px] font-semibold">{score >= 0 ? "+" : ""}{score.toFixed(2)}</text>
    </svg>
  );
}

function Spark({ pts }: { pts: { period: string; score: number }[] }) {
  if (pts.length < 2) return null;
  const w = 160, h = 40;
  const d = pts.map((p, i) => `${(i / (pts.length - 1)) * w},${h / 2 - p.score * (h / 2 - 4)}`).join(" ");
  return (
    <div>
      <svg viewBox={`0 0 ${w} ${h}`} className="h-10 w-40"><polyline points={d} className="fill-none stroke-primary" strokeWidth={2} /></svg>
      <div className="flex w-40 justify-between text-[10px] text-muted-foreground"><span>{pts[0].period}</span><span>{pts[pts.length - 1].period}</span></div>
    </div>
  );
}

function Timeline({ rows }: { rows: { title: string; items: Ev[]; label: string }[] }) {
  return (
    <ol className="grid gap-3 sm:grid-cols-3">
      {rows.map((r) => (
        <li key={r.title} className="rounded-lg border p-3">
          <div className="mb-2 flex items-center justify-between"><span className="text-sm font-semibold">{r.title}</span><Label>{r.label}</Label></div>
          {r.items.length ? (
            r.items.map((e, i) => (
              <div key={i} className="mb-2 text-xs">
                {e.date && <span className="mr-1 font-mono text-muted-foreground">{e.date}</span>}
                {e.quote.slice(0, 160)}
                <Chip ev={e} />
              </div>
            ))
          ) : (
            <p className="text-xs text-muted-foreground">Not found in public sources</p>
          )}
        </li>
      ))}
    </ol>
  );
}

export const SECTIONS = [
  ["snapshot", "Snapshot"], ["profitability", "Profitability"], ["moat", "Moat"], ["stakeholders", "Stakeholders"],
  ["porter", "Five forces"], ["competition", "Competition"], ["tone", "Market attitude"], ["gaps", "Need gaps"],
  ["segments", "Segmentation"], ["positioning", "Positioning"], ["gtm", "Go-to-market"], ["mix", "7P mix"],
  ["todo", "To-do"],
] as const;

export function AnalysisBody({ r, company }: { r: MarketingResult; company: string }) {
  return (
    <div className="space-y-4">
      <Section id="snapshot" title="Snapshot">
        <p className="text-sm">{r.snapshot.summary}</p>
        <div className="mt-3 grid grid-cols-2 gap-x-4 gap-y-2 sm:grid-cols-3">
          {Object.entries(r.snapshot.coverage).map(([k, v]) => (
            <div key={k}>
              <div className="flex justify-between text-xs"><span>{k}</span><span className="text-muted-foreground">{Math.round(v * 100)}%</span></div>
              <div className="h-1.5 rounded-full bg-muted"><div className="h-full rounded-full bg-primary" style={{ width: `${v * 100}%` }} /></div>
            </div>
          ))}
        </div>
        {r.ai_insights?.length ? (
          <div className="mt-4 space-y-2">
            {r.ai_insights.map((c, i) => (
              <div key={i} className="rounded-lg border p-2 text-sm"><Label>{c.label}</Label> {c.claim}
                <Chips ev={c.evidence_ids.map((id) => ({ quote: c.quote ?? c.claim, evidence_id: id }))} />
              </div>
            ))}
          </div>
        ) : null}
      </Section>

      <Section id="profitability" title="Profitability" how={r.profitability.how}>
        {r.profitability.figures.length ? (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead><tr className="text-left text-xs text-muted-foreground"><th className="py-1 pr-2">Metric</th><th className="pr-2">Figure</th><th className="pr-2">Period</th><th>Source</th></tr></thead>
              <tbody>
                {r.profitability.figures.map((f, i) => (
                  <tr key={i} className="border-t align-top">
                    <td className="py-1.5 pr-2">{f.metric}</td><td className="pr-2 font-semibold">{f.value}</td>
                    <td className="pr-2 text-muted-foreground">{f.period ?? "-"}</td><td><Chip ev={f} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
            {r.profitability.trend && <p className="mt-2 text-xs text-muted-foreground">{r.profitability.trend}</p>}
          </div>
        ) : (
          <p className="text-sm"><Label>Not found</Label> Not found in public sources</p>
        )}
      </Section>

      <Section id="moat" title="Moat" how="Each moat type is rated by how many company sentences match its keywords: strong ≥4, moderate 2–3, weak 1, unknown 0.">
        <div className="grid gap-x-6 sm:grid-cols-2">
          {r.moat.map((m) => <RatedRow key={m.dimension} name={m.dimension} rating={m.rating} ev={m.evidence} label={m.label} />)}
        </div>
      </Section>

      <Section id="stakeholders" title="Stakeholders (power / interest)" how="Placement uses a standard default per stakeholder type (Analysis); evidence shows where each appears in the sources.">
        <div className="grid gap-4 md:grid-cols-2">
          <div className="relative grid aspect-square max-h-72 grid-cols-2 grid-rows-2 gap-1 text-[10px]">
            {[["Keep satisfied", "high", "low"], ["Manage closely", "high", "high"], ["Monitor", "low", "low"], ["Keep informed", "low", "high"]].map(([t, p, i]) => (
              <div key={t} className="rounded-md border bg-muted/30 p-1.5">
                <div className="mb-1 font-semibold text-muted-foreground">{t}</div>
                {r.stakeholders.filter((s) => (p === "high" ? s.power === "high" : s.power !== "high") && (i === "high" ? s.interest === "high" : s.interest !== "high")).map((s) => (
                  <span key={s.name} className="mb-1 mr-1 inline-block rounded bg-primary/15 px-1.5 py-0.5 text-[10px] text-foreground">{s.name}</span>
                ))}
              </div>
            ))}
          </div>
          <div className="space-y-2">
            {r.stakeholders.map((s) => (
              <div key={s.name} className="text-sm"><span className="font-medium">{s.name}</span> <span className="text-xs text-muted-foreground">power {s.power} · interest {s.interest}</span><Chips ev={s.evidence} /></div>
            ))}
          </div>
        </div>
      </Section>

      <Section id="porter" title="Porter's Five Forces" how={r.porter.map((p) => `${p.force}: ${p.how}`).join(" ")}>
        <div className="grid gap-4 md:grid-cols-[16rem_1fr]">
          <Radar data={r.porter} />
          <div className="divide-y">
            {r.porter.map((p) => (
              <div key={p.force} className="py-2">
                <div className="flex items-center justify-between text-sm"><span className="font-medium">{p.force}</span><span className={cn("rounded px-2 py-0.5 text-xs font-semibold capitalize text-white", RATING[p.level])}>{p.level}</span></div>
                <p className="text-xs text-muted-foreground">{p.reason} <Label>Analysis</Label></p>
                <Chips ev={p.evidence} />
              </div>
            ))}
          </div>
        </div>
      </Section>

      <Section id="competition" title="Competition" how="Rivals ranked by sentences that mention both the company and the rival.">
        {r.competition.length ? (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead><tr className="text-left text-xs text-muted-foreground"><th className="py-1 pr-2">Rival</th><th className="pr-2">Co-mentions</th><th>What they are doing (evidence)</th></tr></thead>
              <tbody>
                {r.competition.map((c) => (
                  <tr key={c.id} className="border-t align-top">
                    <td className="py-2 pr-2 font-medium">{c.name}</td>
                    <td className="pr-2"><div className="h-2 w-16 rounded bg-muted"><div className="h-full rounded bg-primary" style={{ width: `${Math.min(100, c.co_mentions * 20)}%` }} /></div><span className="text-xs">{c.co_mentions}</span></td>
                    <td className="text-xs">{c.doing[0]?.quote.slice(0, 180)}<Chips ev={c.doing} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : <p className="text-sm text-muted-foreground">Not found in public sources</p>}
      </Section>

      <Section id="tone" title="Market attitude" how="Lexicon score per source: (positive words − negative words) / total, averaged. A transparent word list, not customer sentiment.">
        {r.tone.score === null ? <p className="text-sm text-muted-foreground">Not found in public sources</p> : (
          <div className="flex flex-wrap items-center gap-6">
            <Gauge score={r.tone.score} />
            <Spark pts={r.tone.trend} />
            <p className="text-xs text-muted-foreground">{r.tone.label}</p>
          </div>
        )}
        <div className="mt-3 grid gap-3 sm:grid-cols-2">
          {r.tone.most_positive && <div className="rounded-lg border border-emerald-500/30 p-2 text-xs"><b>Most positive:</b> “{r.tone.most_positive.quote}”<Chip ev={r.tone.most_positive} /></div>}
          {r.tone.most_negative && <div className="rounded-lg border border-rose-500/30 p-2 text-xs"><b>Most negative:</b> “{r.tone.most_negative.quote}”<Chip ev={r.tone.most_negative} /></div>}
        </div>
      </Section>

      <Section id="gaps" title="Need-gap analysis" how="Themes (service, reliability, charging, affordability) where company sentences carry negative tone.">
        {r.need_gaps.length ? r.need_gaps.map((g) => (
          <div key={g.gap} className="mb-2 rounded-lg border p-3 text-sm"><div className="flex items-center gap-2 font-medium">{g.gap} <Label>Analysis</Label></div><p className="text-xs text-muted-foreground">{g.why}</p><Chips ev={g.evidence} /></div>
        )) : <p className="text-sm text-muted-foreground">No negative-tone themes found in the sources.</p>}
      </Section>

      <Section id="segments" title="Segmentation">
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {r.segmentation.map((s) => (
            <div key={s.segment} className="rounded-lg border p-3 text-sm">
              <div className="mb-1 flex items-center justify-between font-medium">{s.segment}<Label>{s.label}</Label></div>
              {s.evidence[0] ? <p className="text-xs">{s.evidence[0].quote.slice(0, 160)}</p> : <p className="text-xs text-muted-foreground">Not found in public sources</p>}
              <Chips ev={s.evidence} />
            </div>
          ))}
        </div>
      </Section>

      <Section id="positioning" title="Positioning: past, present, future" how={r.positioning.map.how}>
        <Timeline rows={[{ title: "Past", items: r.positioning.past, label: "Evidence" }, { title: "Present", items: r.positioning.present, label: "Evidence" }, { title: "Future (stated plans)", items: r.positioning.future, label: "Evidence" }]} />
        {r.positioning.forecast && <p className="mt-2 text-sm"><Label>Forecast</Label> {r.positioning.forecast.replace(/^Forecast:\s*/, "")}</p>}
        <div className="mt-4">
          <div className="mb-1 flex items-center gap-2 text-xs text-muted-foreground">Positioning map <Label>Analysis</Label></div>
          <svg viewBox="0 0 300 200" className="w-full max-w-md rounded-lg border bg-muted/20" role="img" aria-label="Positioning map">
            <line x1={150} y1={10} x2={150} y2={190} className="stroke-border" /><line x1={10} y1={100} x2={290} y2={100} className="stroke-border" />
            <text x={290} y={95} textAnchor="end" className="fill-muted-foreground text-[8px]">{r.positioning.map.x_axis}: premium →</text>
            <text x={154} y={18} className="fill-muted-foreground text-[8px]">↑ {r.positioning.map.y_axis}</text>
            {r.positioning.map.points.map((p) => {
              const x = 20 + p.x * 260, y = 185 - p.y * 170;
              return (
                <g key={p.name}>
                  <circle cx={x} cy={y} r={p.self ? 7 : 5} className={p.self ? "fill-primary" : "fill-muted-foreground/60"} />
                  <text x={x + 9} y={y + 3} className={cn("text-[9px]", p.self ? "fill-foreground font-semibold" : "fill-muted-foreground")}>{p.name}</text>
                </g>
              );
            })}
          </svg>
        </div>
      </Section>

      <Section id="gtm" title="Go-to-market: past, present, future">
        <Timeline rows={[{ title: "Channel & launch timeline", items: r.gtm.timeline.slice(0, 4), label: "Evidence" }, { title: "Recent", items: r.gtm.timeline.slice(4), label: "Evidence" }, { title: "Stated plans", items: r.gtm.future, label: "Evidence" }]} />
        {r.gtm.forecast && <p className="mt-2 text-sm"><Label>Forecast</Label> {r.gtm.forecast.replace(/^Forecast:\s*/, "")}</p>}
      </Section>

      <Section id="mix" title="Marketing mix (7P) scorecard" how="Each P: company sentences matching its keywords. strong = ≥3 cues with positive average tone; weak = negative tone; average otherwise; unknown = no cues.">
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-4 lg:grid-cols-7">
          {r.mix.map((m) => (
            <div key={m.p} className="rounded-lg border p-2 text-center">
              <div className="text-xs font-medium">{m.p}</div>
              <div className={cn("mx-auto my-1 w-fit rounded px-2 py-0.5 text-xs font-semibold capitalize text-white", m.rating === "strong" ? "bg-emerald-500" : m.rating === "weak" ? "bg-rose-500" : m.rating === "average" ? "bg-amber-500" : "bg-muted-foreground/40")}>{m.rating}</div>
              <div className="text-[10px] text-muted-foreground">{m.cues} cues</div>
              <Chips ev={m.evidence.slice(0, 1)} />
            </div>
          ))}
        </div>
      </Section>

      <Section id="todo" title={`Intelligent to-do for ${company}`}>
        <ol className="grid gap-3 md:grid-cols-2">
          {r.recommendations.map((x) => (
            <li key={`${x.priority}-${x.action}`} className="rounded-lg border p-3">
              <div className="mb-1 flex items-start gap-2">
                <span className="grid h-6 w-6 shrink-0 place-items-center rounded-full bg-primary text-xs font-bold text-primary-foreground">{x.priority}</span>
                <span className="text-sm font-medium">{x.action}</span>
              </div>
              <p className="text-xs text-muted-foreground"><b>Why:</b> {x.why}</p>
              <div className="mt-2 flex flex-wrap gap-1.5 text-[10px]">
                {x.impact && <span className="rounded bg-emerald-500/15 px-1.5 py-0.5">Impact: {x.impact}</span>}
                {x.effort && <span className="rounded bg-amber-500/15 px-1.5 py-0.5">Effort: {x.effort}</span>}
                {x.kpi && <span className="rounded bg-sky-500/15 px-1.5 py-0.5">KPI: {x.kpi}</span>}
                <Label>{x.label}</Label>
              </div>
            </li>
          ))}
        </ol>
      </Section>
    </div>
  );
}

const CELL: Record<string, string> = {
  strong: "text-emerald-600 dark:text-emerald-400", low: "text-emerald-600 dark:text-emerald-400",
  high: "text-rose-600 dark:text-rose-400", weak: "text-rose-600 dark:text-rose-400",
  moderate: "text-amber-600 dark:text-amber-400", medium: "text-amber-600 dark:text-amber-400",
  average: "text-amber-600 dark:text-amber-400", unknown: "text-muted-foreground",
};

export function CompareTable({ a, b, nameA, nameB }: { a: MarketingResult; b: MarketingResult; nameA: string; nameB: string }) {
  const rows: [string, string, string, string][] = [
    ...a.porter.map((p, i) => ["Five forces", p.force, p.level, b.porter[i]?.level ?? "unknown"] as [string, string, string, string]),
    ...a.moat.map((m, i) => ["Moat", m.dimension, m.rating, b.moat[i]?.rating ?? "unknown"] as [string, string, string, string]),
    ...a.mix.map((m, i) => ["7P", m.p, m.rating, b.mix[i]?.rating ?? "unknown"] as [string, string, string, string]),
  ];
  const tone = (r: MarketingResult) => (r.tone.score === null ? "n/a" : `${r.tone.score >= 0 ? "+" : ""}${r.tone.score.toFixed(2)}`);
  return (
    <Section id="compare" title={`Head to head: ${nameA} vs ${nameB}`} how="Same rules applied to each company's own evidence. Five forces: high = more pressure (worse); moat and 7P: strong = better.">
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-xs text-muted-foreground"><th className="py-1 pr-2">Framework</th><th className="pr-2">Dimension</th><th className="pr-2">{nameA}</th><th>{nameB}</th></tr>
          </thead>
          <tbody>
            <tr className="border-t"><td className="py-1.5 pr-2 text-xs text-muted-foreground">Snapshot</td><td className="pr-2">Sources</td><td className="pr-2">{a.snapshot.evidence_count}</td><td>{b.snapshot.evidence_count}</td></tr>
            <tr className="border-t"><td className="py-1.5 pr-2 text-xs text-muted-foreground">Attitude</td><td className="pr-2">Indicative tone</td><td className="pr-2">{tone(a)}</td><td>{tone(b)}</td></tr>
            {rows.map(([f, d, x, y]) => (
              <tr key={f + d} className="border-t">
                <td className="py-1.5 pr-2 text-xs text-muted-foreground">{f}</td>
                <td className="pr-2">{d}</td>
                <td className={cn("pr-2 font-medium capitalize", CELL[x])}>{x}</td>
                <td className={cn("font-medium capitalize", CELL[y])}>{y}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="mt-2 text-xs text-muted-foreground"><Label>Analysis</Label> Open each company&apos;s analysis for the evidence behind every rating.</p>
    </Section>
  );
}


const FORCE_RANK: Record<string, number> = { high: 3, medium: 2, low: 1 };
const MOAT_RANK: Record<string, number> = { strong: 4, moderate: 3, weak: 2, unknown: 1 };

/** Four headline takeaways derived only from the sections below (no new facts). */
export function KeyTakeaways({ r, company }: { r: MarketingResult; company: string }) {
  const moat = [...r.moat].sort((a, b) => (MOAT_RANK[b.rating] ?? 0) - (MOAT_RANK[a.rating] ?? 0))[0];
  const force = [...r.porter].sort((a, b) => (FORCE_RANK[b.level] ?? 0) - (FORCE_RANK[a.level] ?? 0))[0];
  const rival = r.competition[0];
  const top = r.recommendations[0];
  const tone = r.tone.score;
  const toneWord = tone === null ? "not enough coverage" : tone > 0.25 ? "upbeat" : tone < -0.1 ? "critical" : "mixed";
  const cards = [
    { icon: Shield, k: "Strongest moat", v: moat && moat.rating !== "unknown" ? `${moat.dimension} (${moat.rating})` : "No moat evidence yet", ev: moat?.evidence },
    { icon: Flame, k: "Biggest pressure", v: force ? `${force.force}: ${force.level}` : "n/a", ev: force?.evidence },
    { icon: GaugeIcon, k: "Media tone", v: tone === null ? toneWord : `${toneWord} (${tone >= 0 ? "+" : ""}${tone.toFixed(2)})${rival ? ` · most compared with ${rival.name}` : ""}`, ev: r.tone.most_positive ? [r.tone.most_positive] : [] },
    { icon: Target, k: "Do this first", v: top ? top.action : "No recommendation triggered", ev: [] as Ev[] },
  ];
  return (
    <div className="mb-4 overflow-hidden rounded-2xl border ring-glow">
      <div className="bg-gradient-to-r from-primary/20 via-primary/5 to-mint/15 px-4 py-3 sm:px-5">
        <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-primary">
          <Sparkles className="h-3.5 w-3.5" /> Key takeaways
        </div>
        <p className="mt-1 text-base font-semibold sm:text-lg">
          {company} in 30 seconds: <span className="text-gradient">{r.snapshot.evidence_count} sources, {r.competition.length} rivals, {r.recommendations.length} moves</span>
        </p>
      </div>
      <div className="grid gap-px bg-border sm:grid-cols-2 lg:grid-cols-4">
        {cards.map((c, i) => (
          <motion.div
            key={c.k}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.08 * i }}
            className="bg-card p-4"
          >
            <div className="mb-1 flex items-center gap-1.5 text-xs text-muted-foreground"><c.icon className="h-3.5 w-3.5 text-primary" /> {c.k}</div>
            <div className="text-sm font-semibold leading-snug">{c.v}</div>
            <div className="mt-1 flex items-center gap-1"><Label>Analysis</Label></div>
            <Chips ev={c.ev?.slice(0, 1)} />
          </motion.div>
        ))}
      </div>
    </div>
  );
}
