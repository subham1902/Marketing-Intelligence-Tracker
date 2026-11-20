"use client";

import { Link2, Loader2, PieChart, Printer, RefreshCw, Search } from "lucide-react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useMemo, useState } from "react";
import { toast } from "sonner";

import { EmptyState } from "@/components/empty-state";
import { AnalysisBody, EvidenceCtx, SECTIONS } from "@/components/marketing/sections";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useCompetitors } from "@/lib/hooks";
import { useAnalyses, useAnalysis, useAnalysisActivity, useStartAnalysis } from "@/lib/marketing-api";
import { cn } from "@/lib/utils";

function useScrollSpy(ids: readonly string[], ready: boolean) {
  const [active, setActive] = useState(ids[0]);
  useEffect(() => {
    if (!ready) return;
    const obs = new IntersectionObserver(
      (es) => es.forEach((e) => e.isIntersecting && setActive(e.target.id)),
      { rootMargin: "-30% 0px -60% 0px" },
    );
    ids.forEach((id) => {
      const el = document.getElementById(id);
      if (el) obs.observe(el);
    });
    return () => obs.disconnect();
  }, [ids, ready]);
  return active;
}

function MarketingView() {
  const sp = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const companies = useCompetitors();
  const company = sp.get("company") ?? "";
  const explicitId = sp.get("id") ?? "";
  const list = useAnalyses(company || undefined);
  const latest = list.data?.find((a) => a.status === "completed") ?? list.data?.[0];
  const [runId, setRunId] = useState<string>("");
  const id = explicitId || runId || latest?.id || "";
  const analysis = useAnalysis(id || undefined);
  useAnalysisActivity(analysis.data);
  const start = useStartAnalysis();
  const [custom, setCustom] = useState("");
  const ids = useMemo(() => SECTIONS.map((s) => s[0]), []);
  const a = analysis.data;
  const ready = a?.status === "completed" && !!a.result;
  const active = useScrollSpy(ids, ready);
  const evMap = useMemo(() => new Map((a?.evidence ?? []).map((e) => [e.id, e])), [a?.evidence]);

  const setParam = (k: string, v: string) => {
    const q = new URLSearchParams();
    if (v) q.set(k, v);
    setRunId("");
    router.push(`${pathname}?${q.toString()}`);
  };
  const run = (body: { company?: string; name?: string }) =>
    start.mutate(body, {
      onSuccess: (r) => {
        setRunId(r.id);
        if (body.name) router.push(`${pathname}?id=${encodeURIComponent(r.id)}`);
      },
    });

  const copyLink = async () => {
    const url = `${window.location.origin}${pathname}?id=${encodeURIComponent(id)}`;
    try {
      await navigator.clipboard.writeText(url);
      toast.success("Share link copied");
    } catch {
      toast.message(url);
    }
  };

  const running = a && (a.status === "queued" || a.status === "running");
  const name = a?.company_name ?? companies.data?.find((c) => c.id === company)?.name ?? "";

  return (
    <div className="pb-10">
      <div className="mb-4 flex flex-col gap-3 print:hidden">
        <div className="flex items-center gap-2">
          <PieChart className="h-5 w-5 text-primary" />
          <h1 className="text-xl font-semibold tracking-tight">Marketing Analysis</h1>
        </div>
        <p className="text-sm text-muted-foreground">
          A consultant-style strategy deck in seconds: moat, Five Forces, stakeholders, positioning, 7P and a to-do list. Every claim links to a public source or is labelled Analysis / Forecast.
        </p>
        <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
          <select
            aria-label="Company"
            className="h-9 rounded-md border bg-background px-2 text-sm"
            value={company}
            onChange={(e) => setParam("company", e.target.value)}
          >
            <option value="">All recent analyses</option>
            {(companies.data ?? []).map((c) => (
              <option key={c.id} value={c.id}>{c.name}</option>
            ))}
          </select>
          <form
            className="flex flex-1 gap-2"
            onSubmit={(e) => {
              e.preventDefault();
              if (custom.trim()) run({ name: custom.trim() });
            }}
          >
            <input
              value={custom}
              onChange={(e) => setCustom(e.target.value)}
              placeholder="Analyse any company…"
              className="h-9 min-w-0 flex-1 rounded-md border bg-background px-3 text-sm"
              aria-label="Analyse any company"
            />
            <Button type="submit" size="sm" disabled={!custom.trim() || start.isPending}>
              <Search className="mr-1 h-4 w-4" /> Analyse
            </Button>
          </form>
        </div>
      </div>

      {a && (
        <div className="mb-4 flex flex-wrap items-center gap-2 rounded-xl border bg-card p-3">
          <span className="text-lg font-semibold">{name}</span>
          <Badge variant={a.mode === "ai" ? "default" : "secondary"}>{a.mode === "ai" ? "AI-assisted" : "Rule-based"}</Badge>
          {a.result && <Badge variant="muted">{a.result.snapshot.evidence_count} sources · {a.result.snapshot.fetched_count} read in full</Badge>}
          <span className="text-xs text-muted-foreground">
            {a.is_snapshot ? "Captured" : "Run"} {(a.completed_at ?? a.created_at).slice(0, 10)}
          </span>
          <span className="ml-auto flex flex-wrap gap-2 print:hidden">
            <Button size="sm" variant="outline" disabled={!!running || start.isPending}
              onClick={() => run(company && company === a.company ? { company } : a.is_snapshot || companies.data?.some((c) => c.id === a.company) ? { company: a.company } : { name })}>
              <RefreshCw className={cn("mr-1 h-4 w-4", running && "animate-spin")} /> Refresh
            </Button>
            <Button size="sm" variant="outline" onClick={copyLink} disabled={!ready}><Link2 className="mr-1 h-4 w-4" /> Copy share link</Button>
            <Button size="sm" variant="outline" onClick={() => window.print()} disabled={!ready}><Printer className="mr-1 h-4 w-4" /> Download PDF</Button>
          </span>
        </div>
      )}

      {(list.isLoading || analysis.isLoading) && <Skeleton className="h-64 w-full" />}

      {!list.isLoading && !id && (
        <EmptyState icon={PieChart} title="Run your first analysis" description="Pick a tracked company or type any company name above." />
      )}

      {running && (
        <div className="rounded-xl border bg-card p-6 text-sm">
          <div className="flex items-center gap-2 font-medium"><Loader2 className="h-4 w-4 animate-spin" /> {a?.stage ?? "Queued"}</div>
          <p className="mt-1 text-muted-foreground">Gathering evidence → Reading sources → Analysing → Done. Usually under a minute.</p>
          {latest && latest.id !== a?.id && latest.status === "completed" && (
            <button className="mt-2 text-primary hover:underline" onClick={() => setRunId(latest.id)}>Open the latest captured analysis</button>
          )}
        </div>
      )}

      {a?.status === "failed" && (
        <div className="rounded-xl border border-rose-500/40 bg-card p-4 text-sm">
          <p className="font-medium">This analysis could not finish.</p>
          <p className="text-muted-foreground">{a.error}</p>
          {list.data?.find((x) => x.status === "completed") && (
            <button className="mt-2 text-primary hover:underline" onClick={() => setRunId(list.data!.find((x) => x.status === "completed")!.id)}>
              Open the latest captured analysis
            </button>
          )}
        </div>
      )}

      {ready && a.result && (
        <EvidenceCtx.Provider value={evMap}>
          <div className="lg:grid lg:grid-cols-[11rem_1fr] lg:gap-6">
            <nav aria-label="Sections" className="sticky top-14 z-20 -mx-4 mb-3 flex gap-1 overflow-x-auto bg-background/90 px-4 py-2 backdrop-blur lg:top-20 lg:mx-0 lg:mb-0 lg:block lg:h-fit lg:space-y-0.5 lg:bg-transparent lg:p-0 print:hidden">
              {SECTIONS.map(([sid, label]) => (
                <a key={sid} href={`#${sid}`}
                  className={cn("shrink-0 whitespace-nowrap rounded-full px-3 py-1 text-xs lg:block lg:rounded-md lg:text-sm",
                    active === sid ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:bg-muted")}>
                  {label}
                </a>
              ))}
            </nav>
            <div className="min-w-0">
              <h1 className="mb-3 hidden text-2xl font-bold print:block">Marketing Analysis: {name}</h1>
              <AnalysisBody r={a.result} company={name} />
              <p className="mt-6 text-xs text-muted-foreground">
                Labels: Evidence = quoted from a fetched public source · Analysis = transparent rule over that evidence · Forecast = projection from stated plans · AI analysis = model output checked against the cited quote.
              </p>
            </div>
          </div>
        </EvidenceCtx.Provider>
      )}
    </div>
  );
}

export default function MarketingPage() {
  return (
    <Suspense fallback={<Skeleton className="h-64 w-full" />}>
      <MarketingView />
    </Suspense>
  );
}
