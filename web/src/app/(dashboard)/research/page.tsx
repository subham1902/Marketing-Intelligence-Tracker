"use client";

import { FlaskConical, Inbox, KeyRound, Play, Sparkles } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { AsyncState } from "@/components/async-state";
import { EmptyState } from "@/components/empty-state";
import { PageHeader } from "@/components/page-header";
import { RunRow } from "@/components/research/research-ui";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { useCompetitors } from "@/lib/hooks";
import { useCreateResearch, useResearchConfig, useResearchRuns } from "@/lib/research-api";
import {
  PREFERENCE_LABEL,
  SOURCE_PREFERENCES,
  WINDOW_LABEL,
  type SourcePreference,
  type TimeWindow,
} from "@/lib/research-types";
import { cn } from "@/lib/utils";

const EXAMPLE =
  "Research India's electric mobility industry over the last six months. Identify significant competitor developments, product launches, manufacturing expansions, partnerships, investment activity, policy developments, procurement opportunities and emerging commercial opportunities. Prioritize original company announcements and official government sources. Separate verified facts from analysis and provide the sources supporting every finding.";

const TEMPLATES: { label: string; objective: string; prefs: SourcePreference[]; window: TimeWindow }[] = [
  { label: "Market overview", objective: EXAMPLE, prefs: ["official_company", "government", "tenders"], window: "3m" },
  {
    label: "Policy & incentives",
    objective: "Government policy, subsidy and incentive developments for electric vehicles in India (PM E-DRIVE, PLI, state EV policies).",
    prefs: ["government", "regulatory"],
    window: "3m",
  },
  {
    label: "Tenders & procurement",
    objective: "Public tenders and procurement for electric buses, EV charging infrastructure and batteries in India.",
    prefs: ["tenders", "government"],
    window: "3m",
  },
  {
    label: "Competitor moves",
    objective: "Product launches, partnerships, funding and expansion announcements by Indian EV makers.",
    prefs: ["official_company", "news"],
    window: "1m",
  },
];

const GEOS = ["India", "South India", "North India", "West India", "East India", "Global (India focus)"];

export default function ResearchPage() {
  const router = useRouter();
  const config = useResearchConfig();
  const runs = useResearchRuns();
  const competitors = useCompetitors();
  const create = useCreateResearch();

  const [objective, setObjective] = useState(EXAMPLE);
  const [industry, setIndustry] = useState("Electric vehicles & mobility");
  const [geography, setGeography] = useState("India");
  const [timeWindow, setTimeWindow] = useState<TimeWindow>("6m");
  const [prefs, setPrefs] = useState<SourcePreference[]>(["official_company", "government", "tenders"]);
  const [useTracked, setUseTracked] = useState(true);

  const live = config.data?.live_available ?? false;
  const tracked = (competitors.data ?? []).map((c) => c.name);
  const tooShort = objective.trim().length < 10;

  const togglePref = (p: SourcePreference) =>
    setPrefs((cur) => (cur.includes(p) ? cur.filter((x) => x !== p) : [...cur, p]));

  const submit = () =>
    create.mutate(
      {
        objective: objective.trim(),
        industry: industry.trim() || null,
        geography,
        time_window: timeWindow,
        companies: useTracked ? tracked.slice(0, 12) : [],
        source_preferences: prefs,
      },
      {
        onSuccess: (run) => {
          if (run.status !== "failed") router.push(`/research/view?id=${encodeURIComponent(run.id)}`);
        },
      },
    );

  return (
    <div>
      <PageHeader
        title="Research workspace"
        description="Ask a market question. The research provider reads the web and returns structured, source-linked findings."
      />

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-5">
        <Card className="lg:col-span-3">
          <CardHeader>
            <CardTitle className="text-base">New research objective</CardTitle>
            <CardDescription>
              {config.isLoading ? (
                "Checking provider…"
              ) : live ? (
                <span className="inline-flex items-center gap-1.5 text-emerald-700 dark:text-emerald-400">
                  <Sparkles className="h-3.5 w-3.5" />{" "}
                  {config.data?.provider === "open"
                    ? `Free public sources (no key) · ${config.data?.synthesis ?? "extractive"}`
                    : `Live research via ${config.data?.provider} (${config.data?.mode} mode)`}
                  <button
                    type="button"
                    onClick={() => window.dispatchEvent(new Event("open-llm-panel"))}
                    className="ml-1 font-medium text-primary underline-offset-2 hover:underline"
                  >
                    {config.data?.synthesis?.startsWith("AI") ? "Change AI summaries" : "Connect LLM for AI summaries"}
                  </button>
                </span>
              ) : (
                <span className="inline-flex items-center gap-1.5 text-amber-700 dark:text-amber-400">
                  <KeyRound className="h-3.5 w-3.5" /> Live research not configured. Set COMPETE_RESEARCH_PROVIDER=open (free) or a CONTEXT_DEV_API_KEY on the server. The demo snapshot below is still browsable.
                </span>
              )}
            </CardDescription>
          </CardHeader>
          <CardContent className="flex flex-col gap-4">
            <div className="flex flex-wrap gap-2">
              {TEMPLATES.map((t) => (
                <button
                  key={t.label}
                  type="button"
                  onClick={() => {
                    setObjective(t.objective);
                    setPrefs(t.prefs);
                    setTimeWindow(t.window);
                  }}
                  className="rounded-md border border-dashed px-2.5 py-1 text-xs text-muted-foreground transition-colors hover:border-primary hover:text-foreground"
                >
                  {t.label}
                </button>
              ))}
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="objective">Research objective</Label>
              <textarea
                id="objective"
                value={objective}
                onChange={(e) => setObjective(e.target.value)}
                maxLength={1200}
                rows={6}
                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              />
              <span className="text-right text-xs text-muted-foreground">{objective.length}/1200</span>
            </div>

            <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="industry">Industry</Label>
                <Input id="industry" value={industry} onChange={(e) => setIndustry(e.target.value)} maxLength={120} />
              </div>
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="geo">Geography</Label>
                <Select id="geo" value={geography} onChange={(e) => setGeography(e.target.value)}>
                  {GEOS.map((g) => (
                    <option key={g}>{g}</option>
                  ))}
                </Select>
              </div>
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="window">Time window</Label>
                <Select id="window" value={timeWindow} onChange={(e) => setTimeWindow(e.target.value as TimeWindow)}>
                  {(Object.keys(WINDOW_LABEL) as TimeWindow[]).map((w) => (
                    <option key={w} value={w}>
                      {WINDOW_LABEL[w]}
                    </option>
                  ))}
                </Select>
              </div>
            </div>

            <div className="flex flex-col gap-1.5">
              <Label>Source preferences</Label>
              <div className="flex flex-wrap gap-2">
                {SOURCE_PREFERENCES.map((p) => {
                  const on = prefs.includes(p);
                  return (
                    <button
                      key={p}
                      type="button"
                      onClick={() => togglePref(p)}
                      aria-pressed={on}
                      className={cn(
                        "rounded-full border px-3 py-1 text-xs font-medium transition-colors",
                        on ? "border-primary bg-primary/15 text-foreground" : "text-muted-foreground hover:bg-secondary",
                      )}
                    >
                      {PREFERENCE_LABEL[p]}
                    </button>
                  );
                })}
              </div>
            </div>

            <label className="flex items-start gap-2 text-sm">
              <input
                type="checkbox"
                checked={useTracked}
                onChange={(e) => setUseTracked(e.target.checked)}
                className="mt-0.5"
              />
              <span>
                Focus on tracked companies
                <span className="block text-xs text-muted-foreground">
                  {tracked.length ? tracked.join(", ") : "No companies tracked yet"}
                </span>
              </span>
            </label>

            <div className="flex flex-wrap items-center gap-3">
              <Button onClick={submit} disabled={tooShort || create.isPending || !live}>
                <Play className="h-4 w-4" />
                {create.isPending ? "Submitting…" : "Run research"}
              </Button>
              <span className="text-xs text-muted-foreground">
                {config.data?.provider === "open"
                  ? "Free: DuckDuckGo news, Google News, PIB and GDELT. No credits used."
                  : "One run uses ~12 provider credits (fast answer + source enrichment)."}
              </span>
            </div>
          </CardContent>
        </Card>

        <div className="lg:col-span-2">
          <h2 className="mb-3 font-display text-base font-semibold text-foreground">
            Research runs
          </h2>
          <AsyncState
            isLoading={runs.isLoading}
            isError={runs.isError}
            error={runs.error}
            onRetry={() => runs.refetch()}
            isEmpty={(runs.data?.length ?? 0) === 0}
            skeleton={
              <div className="flex flex-col gap-3">
                {Array.from({ length: 3 }).map((_, i) => (
                  <Skeleton key={i} className="h-20 w-full" />
                ))}
              </div>
            }
            empty={<EmptyState icon={Inbox} title="No research yet" description="Submit an objective to start." />}
          >
            <div className="flex flex-col gap-3">
              {runs.data?.map((r) => <RunRow key={r.id} run={r} />)}
            </div>
          </AsyncState>
          <p className="mt-4 flex items-start gap-1.5 text-xs text-muted-foreground">
            <FlaskConical className="mt-0.5 h-3.5 w-3.5 shrink-0" />
            Runs marked “Demo snapshot” are preloaded sample data, not live research.
          </p>
        </div>
      </div>
    </div>
  );
}
