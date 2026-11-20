"use client";

import { ArrowLeft, ExternalLink, FileSearch, Globe, Loader2 } from "lucide-react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useMemo } from "react";

import { AsyncState } from "@/components/async-state";
import { EmptyState } from "@/components/empty-state";
import { RelativeTime } from "@/components/relative-time";
import { DataOriginBadge, FindingCard, StageBar, StatusBadge } from "@/components/research/research-ui";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useResearchFindings, useResearchRun, useResearchSources } from "@/lib/research-api";
import type { ResearchReport, ResearchSource } from "@/lib/research-types";

const SECTIONS: { key: keyof ResearchReport; title: string }[] = [
  { key: "market_trends", title: "Market trends" },
  { key: "company_developments", title: "Company developments" },
  { key: "product_launches", title: "Product launches" },
  { key: "manufacturing_expansion", title: "Manufacturing expansion" },
  { key: "partnerships_and_investment", title: "Partnerships & investment" },
  { key: "policy_and_regulatory", title: "Policy & regulatory developments" },
  { key: "tenders_and_procurement", title: "Tenders & procurement" },
  { key: "commercial_opportunities", title: "Opportunities" },
  { key: "risks", title: "Risks" },
];

function ReportView() {
  const id = useSearchParams().get("id") ?? "";
  const run = useResearchRun(id);
  const done = run.data?.status === "completed" || run.data?.status === "partial";
  const sources = useResearchSources(id, done);
  const findings = useResearchFindings(id, done);

  const sourceMap = useMemo(
    () => new Map<string, ResearchSource>((sources.data ?? []).map((s) => [s.id, s])),
    [sources.data],
  );

  if (!id)
    return <EmptyState icon={FileSearch} title="No report selected" description="Open a run from the Research workspace." />;

  return (
    <div>
      <Link href="/research" className="mb-4 inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground">
        <ArrowLeft className="h-4 w-4" /> Research workspace
      </Link>

      <AsyncState
        isLoading={run.isLoading}
        isError={run.isError}
        error={run.error}
        onRetry={() => run.refetch()}
        skeleton={<Skeleton className="h-40 w-full" />}
      >
        {run.data && (
          <>
            <div className="mb-6">
              <div className="flex flex-wrap items-center gap-2">
                <StatusBadge status={run.data.status} />
                <DataOriginBadge isDemo={run.data.is_demo} provider={run.data.provider} />
                {run.data.industry && <Badge variant="secondary">{run.data.industry}</Badge>}
                {run.data.geography && <Badge variant="secondary">{run.data.geography}</Badge>}
                {run.data.date_from && run.data.date_to && (
                  <Badge variant="secondary">
                    {run.data.date_from} → {run.data.date_to}
                  </Badge>
                )}
              </div>
              <h1 className="mt-3 text-xl font-semibold tracking-tight sm:text-2xl">Research report</h1>
              <p className="mt-1 max-w-4xl text-sm text-muted-foreground">{run.data.objective}</p>
              <p className="mt-1 text-xs text-muted-foreground">
                Submitted <RelativeTime value={run.data.created_at} className="text-xs" />
                {run.data.completed_at && (
                  <>
                    {" "}· finished <RelativeTime value={run.data.completed_at} className="text-xs" />
                  </>
                )}
                {run.data.provider_request_id && ` · provider request ${run.data.provider_request_id}`}
                {run.data.result?.method && ` · method: ${run.data.result.method}`}
              </p>
            </div>

            {(run.data.status === "queued" || run.data.status === "running") && (
              <Card className="mb-6">
                <CardContent className="flex flex-col gap-4 py-6">
                  <StageBar status={run.data.status} message={run.data.status_message} />
                  <div>
                    <p className="text-sm font-medium">
                      {run.data.status === "queued"
                        ? "Queued on the backend"
                        : (run.data.status_message ?? "The research provider is working")}
                    </p>
                    <p className="mt-1 text-sm text-muted-foreground">
                      {run.data.provider === "open"
                        ? "Stages reported by the backend: discovering sources, fetching pages, synthesizing. Typically 30-120 s."
                        : "The provider searches, reads pages and assembles a structured answer in a single call (typically 30-180 s)."}{" "}
                      This page checks the backend every 3 seconds.
                    </p>
                  </div>
                </CardContent>
              </Card>
            )}

            {run.data.status === "failed" && (
              <div className="mb-6 rounded-lg border border-destructive/30 bg-destructive/5 p-4">
                <p className="text-sm font-medium text-destructive">Research failed{run.data.error_code ? ` (${run.data.error_code})` : ""}</p>
                <p className="mt-1 text-sm text-muted-foreground">{run.data.error_message}</p>
              </div>
            )}

            {run.data.status === "partial" && (
              <div className="mb-6 rounded-lg border border-amber-500/30 bg-amber-500/5 p-3 text-sm text-amber-800 dark:text-amber-300">
                The provider hit its time limit; this report uses the evidence gathered so far.
              </div>
            )}

            {done && run.data.result && (
              <Tabs defaultValue="report">
                <TabsList>
                  <TabsTrigger value="report">Report</TabsTrigger>
                  <TabsTrigger value="findings">Findings ({run.data.finding_count})</TabsTrigger>
                  <TabsTrigger value="sources">Sources ({run.data.source_count})</TabsTrigger>
                </TabsList>

                <TabsContent value="report" className="mt-4 flex flex-col gap-4">
                  <Card>
                    <CardHeader className="pb-2">
                      <CardTitle className="text-base">Executive summary</CardTitle>
                    </CardHeader>
                    <CardContent className="text-sm leading-relaxed">
                      {run.data.result.method?.startsWith("llm") && (
                        <p className="mb-2 rounded-md border border-amber-500/30 bg-amber-500/5 px-2 py-1 text-xs text-amber-800 dark:text-amber-300">
                          AI-written summary from a local model. Not quote-verified and may contain errors; rely on the source-supported findings and sources.
                        </p>
                      )}
                      {run.data.result.executive_summary ?? <span className="text-muted-foreground">Not provided.</span>}
                    </CardContent>
                  </Card>
                  {run.data.result.industry_overview && (
                    <Card>
                      <CardHeader className="pb-2">
                        <CardTitle className="text-base">Industry overview</CardTitle>
                      </CardHeader>
                      <CardContent className="text-sm leading-relaxed">{run.data.result.industry_overview}</CardContent>
                    </Card>
                  )}
                  <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                    {SECTIONS.map(({ key, title }) => {
                      const items = (run.data!.result![key] as string[]) ?? [];
                      if (!items.length) return null;
                      return (
                        <Card key={key}>
                          <CardHeader className="pb-2">
                            <CardTitle className="text-base">{title}</CardTitle>
                          </CardHeader>
                          <CardContent>
                            <ul className="list-disc space-y-1.5 pl-4 text-sm">
                              {items.map((t, i) => (
                                <li key={i}>{t}</li>
                              ))}
                            </ul>
                          </CardContent>
                        </Card>
                      );
                    })}
                  </div>
                  {(run.data.result.coverage_notes?.length ?? 0) > 0 && (
                    <Card>
                      <CardHeader className="pb-2">
                        <CardTitle className="text-base">Coverage notes</CardTitle>
                      </CardHeader>
                      <CardContent>
                        <ul className="list-disc space-y-1 pl-4 text-xs text-muted-foreground">
                          {run.data.result.coverage_notes!.map((n, i) => (
                            <li key={i}>{n}</li>
                          ))}
                        </ul>
                      </CardContent>
                    </Card>
                  )}
                  <p className="text-xs text-muted-foreground">
                    {run.data.result.method === "extractive"
                      ? "Extractive mode: section items are source headlines; finding summaries are verbatim source text. No generated prose."
                      : run.data.result.method?.startsWith("llm")
                        ? `Sections written by ${run.data.result.method}. Only findings whose quote was found in the cited source are marked source-supported.`
                        : "Section text is the provider synthesis. Use the Findings tab for item-level source links and the fact / analysis distinction."}
                  </p>
                </TabsContent>

                <TabsContent value="findings" className="mt-4">
                  <AsyncState
                    isLoading={findings.isLoading}
                    isError={findings.isError}
                    error={findings.error}
                    isEmpty={(findings.data?.length ?? 0) === 0}
                    skeleton={<Skeleton className="h-40 w-full" />}
                    empty={<EmptyState icon={FileSearch} title="No structured findings returned" />}
                  >
                    <div className="flex flex-col gap-3">
                      {findings.data?.map((f) => <FindingCard key={f.id} finding={f} sources={sourceMap} />)}
                    </div>
                  </AsyncState>
                </TabsContent>

                <TabsContent value="sources" className="mt-4">
                  <AsyncState
                    isLoading={sources.isLoading}
                    isError={sources.isError}
                    error={sources.error}
                    isEmpty={(sources.data?.length ?? 0) === 0}
                    skeleton={<Skeleton className="h-40 w-full" />}
                    empty={<EmptyState icon={Globe} title="No sources returned" />}
                  >
                    <div className="overflow-hidden rounded-lg border">
                      {sources.data?.map((s) => (
                        <div key={s.id} className="flex flex-col gap-1 border-b p-3 last:border-b-0 sm:flex-row sm:items-start sm:gap-4">
                          <div className="min-w-0 flex-1">
                            <div className="flex flex-wrap items-center gap-2">
                              <Badge variant="secondary" className="capitalize">{s.source_type ?? "web"}</Badge>
                              <span className="text-sm font-medium">{s.domain}</span>
                              {s.link_status === "dead" && (
                                <Badge variant="outline" className="border-destructive/40 text-destructive">Link unreachable</Badge>
                              )}
                              {s.link_status === "ok" && (
                                <Badge variant="outline" className="text-muted-foreground">Link checked</Badge>
                              )}
                            </div>
                            {s.title && <p className="mt-1 text-sm">{s.title}</p>}
                            <p className="mt-0.5 text-xs text-muted-foreground">
                              Published:{" "}
                              {s.published_at
                                ? new Date(s.published_at).toLocaleDateString("en-IN", {
                                    day: "numeric",
                                    month: "short",
                                    year: "numeric",
                                  })
                                : "Not available"}
                              {s.discovered_via && ` · via ${s.discovered_via.replace("_", " ")}`}
                            </p>
                            <p className="mt-0.5 break-all text-xs text-muted-foreground">{s.url}</p>
                            {s.snippet && <p className="mt-1 line-clamp-3 text-xs text-muted-foreground">{s.snippet}</p>}
                          </div>
                          <a
                            href={s.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="inline-flex shrink-0 items-center gap-1 text-sm text-primary hover:underline"
                          >
                            Open source <ExternalLink className="h-3.5 w-3.5" />
                          </a>
                        </div>
                      ))}
                    </div>
                  </AsyncState>
                </TabsContent>
              </Tabs>
            )}
          </>
        )}
      </AsyncState>
    </div>
  );
}

export default function ResearchViewPage() {
  return (
    <Suspense fallback={<Skeleton className="h-40 w-full" />}>
      <ReportView />
    </Suspense>
  );
}
