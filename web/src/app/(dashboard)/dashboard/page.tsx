"use client";

import { AreaChart, BarChart, DonutChart, SparkAreaChart } from "@/components/charts";
import { Activity, Bell, Building2, FlaskConical, Signal as SignalIcon, TrendingUp, Inbox, PieChart, ArrowRight } from "lucide-react";
import Link from "next/link";

import { AsyncState } from "@/components/async-state";
import { ChartCard } from "@/components/chart-card";
import { CompetitorAvatar } from "@/components/competitor-avatar";
import { EmptyState } from "@/components/empty-state";
import { PageHeader } from "@/components/page-header";
import { FindingCard, RunRow } from "@/components/research/research-ui";
import { RunPipelineButton } from "@/components/run-pipeline-button";
import { SignalCard } from "@/components/signal-card";
import { StatCard } from "@/components/stat-card";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useCompetitors, useOverview, useSignals } from "@/lib/hooks";
import { useFindingCategories, useFindingsFeed, useResearchRuns } from "@/lib/research-api";
import { CATEGORY_LABEL, type FindingCategory } from "@/lib/research-types";
import { signalMeta } from "@/lib/signal-meta";

// Verified evidence first; unverified analysis last.
const KIND_RANK: Record<string, number> = {
  source_supported: 0,
  verified_fact: 1,
  source_excerpt: 2,
  analysis: 3,
};

export default function OverviewPage() {
  const overview = useOverview();
  const signals = useSignals({ limit: 8 });
  const competitors = useCompetitors();
  const findings = useFindingsFeed({ limit: 50, include_demo: false });
  const runs = useResearchRuns();
  const cats = useFindingCategories();
  const catData = (cats.data ?? []).map((c) => ({
    name: CATEGORY_LABEL[c.category as FindingCategory] ?? c.category,
    Findings: c.count,
  }));

  const nameById = new Map((competitors.data ?? []).map((c) => [c.id, c.name]));
  const stats = overview.data;
  const trend = stats?.weekly_trend ?? [];

  const donutData = (stats?.by_type ?? []).map((t) => ({
    name: signalMeta(t.signal_type).label,
    value: t.count,
  }));
  const donutColors = (stats?.by_type ?? []).map((t) => signalMeta(t.signal_type).tremor);

  return (
    <div>
      <PageHeader
        title="Overview"
        description="Market research findings and company signals in one view."
        actions={<RunPipelineButton />}
      />

      <Link
        href="/marketing?company=ather-energy"
        className="group mb-5 flex flex-col gap-3 overflow-hidden rounded-2xl border bg-gradient-to-r from-primary/20 via-primary/5 to-mint/15 p-4 ring-glow transition hover:-translate-y-0.5 sm:flex-row sm:items-center sm:p-5"
      >
        <div className="grid h-11 w-11 shrink-0 place-items-center rounded-xl bg-primary text-primary-foreground shadow-lg">
          <PieChart className="h-5 w-5" />
        </div>
        <div className="min-w-0 flex-1">
          <div className="text-xs font-semibold uppercase tracking-wider text-primary">New · Marketing Analysis</div>
          <div className="text-base font-semibold sm:text-lg">A consultant-grade strategy deck on any company, in 30 seconds</div>
          <p className="text-sm text-muted-foreground">Moat, Five Forces, positioning, 7P and a prioritised to-do list. Every claim links to its public source.</p>
        </div>
        <span className="inline-flex items-center gap-1 text-sm font-medium text-primary">
          Open Ather&apos;s deck <ArrowRight className="h-4 w-4 transition group-hover:translate-x-1" />
        </span>
      </Link>

      {/* Metric cards: 2-up on phones, 4-up once there's room. */}
      <div className="grid grid-cols-2 gap-3 sm:gap-4 lg:grid-cols-4">
        <StatCard
          label="Companies tracked"
          value={stats?.competitors_tracked ?? "-"}
          icon={Building2}
          loading={overview.isLoading}
        />
        <StatCard
          label="Signals this week"
          value={stats?.signals_this_week ?? "-"}
          icon={SignalIcon}
          hint={stats ? `${stats.signals_total} total` : undefined}
          loading={overview.isLoading}
        >
          {trend.length > 0 && (
            <SparkAreaChart
              data={trend}
              categories={["total_changes"]}
              index="week"
              colors={["teal"]}
              className="h-9 w-full"
            />
          )}
        </StatCard>
        <StatCard
          label="High significance"
          value={stats?.high_significance_count ?? "-"}
          icon={TrendingUp}
          hint="weighted ≥ 4"
          loading={overview.isLoading}
        />
        <StatCard
          label="Active alerts"
          value={stats?.active_alerts ?? "-"}
          icon={Bell}
          hint="last 7 days"
          accent={stats && stats.active_alerts > 0 ? "bg-destructive/10 text-destructive" : undefined}
          loading={overview.isLoading}
        />
      </div>

      {/* Market research: latest runs + important findings */}
      <div className="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <div className="mb-3 flex items-center justify-between">
            <h2 className="font-display text-base font-semibold text-foreground">
              Latest live developments
            </h2>
            <Link href="/feed" className="text-sm text-primary hover:underline">
              Intelligence feed
            </Link>
          </div>
          <AsyncState
            isLoading={findings.isLoading}
            isError={findings.isError}
            error={findings.error}
            onRetry={() => findings.refetch()}
            isEmpty={(findings.data?.items.length ?? 0) === 0}
            skeleton={<Skeleton className="h-40 w-full" />}
            empty={
              <EmptyState
                icon={FlaskConical}
                title="No live findings yet"
                description="Run a research objective to populate market developments."
              />
            }
          >
            <div className="flex flex-col gap-3">
              {[...(findings.data?.items ?? [])]
                .sort(
                  (a, b) =>
                    KIND_RANK[a.kind] - KIND_RANK[b.kind] ||
                    (b.significance ?? 0) - (a.significance ?? 0),
                )
                .slice(0, 4)
                .map((f) => (
                  <FindingCard key={f.id} finding={f} showRun />
                ))}
            </div>
          </AsyncState>
        </div>
        <div>
          <div className="mb-3 flex items-center justify-between">
            <h2 className="font-display text-base font-semibold text-foreground">
              Recent research
            </h2>
            <Link href="/research" className="text-sm text-primary hover:underline">
              New research
            </Link>
          </div>
          <AsyncState
            isLoading={runs.isLoading}
            isError={runs.isError}
            error={runs.error}
            onRetry={() => runs.refetch()}
            isEmpty={(runs.data?.length ?? 0) === 0}
            skeleton={<Skeleton className="h-40 w-full" />}
            empty={<EmptyState icon={FlaskConical} title="No research runs" />}
          >
            <div className="flex flex-col gap-3">
              {runs.data?.slice(0, 4).map((r) => <RunRow key={r.id} run={r} />)}
            </div>
          </AsyncState>
        </div>
      </div>

      <div className="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-3">
        {/* Recent signals feed */}
        <div className="lg:col-span-2">
          <div className="mb-3 flex items-center justify-between">
            <h2 className="font-display text-base font-semibold text-foreground">
              Recent signals
            </h2>
            <Link href="/signals" className="text-sm text-primary hover:underline">
              View all signals
            </Link>
          </div>
          <AsyncState
            isLoading={signals.isLoading}
            isError={signals.isError}
            error={signals.error}
            onRetry={() => signals.refetch()}
            isEmpty={(signals.data?.items.length ?? 0) === 0}
            skeleton={
              <div className="flex flex-col gap-3">
                {Array.from({ length: 5 }).map((_, i) => (
                  <Skeleton key={i} className="h-24 w-full" />
                ))}
              </div>
            }
            empty={
              <EmptyState
                icon={Inbox}
                title="No signals yet"
                description="Run the pipeline or seed demo data to populate the feed."
                action={<RunPipelineButton />}
              />
            }
          >
            <div className="flex flex-col gap-3">
              {signals.data?.items.map((s) => (
                <SignalCard
                  key={s.signal_id}
                  signal={s}
                  competitorName={nameById.get(s.competitor_id)}
                />
              ))}
            </div>
          </AsyncState>
        </div>

        {/* Right column */}
        <div className="flex flex-col gap-6">
          <ChartCard title="Market pulse" description="Research findings by category (all runs)">
            {cats.isLoading ? (
              <Skeleton className="h-52 w-full" />
            ) : catData.length === 0 ? (
              <p className="py-10 text-center text-sm text-muted-foreground">No findings yet</p>
            ) : (
              <BarChart
                data={catData}
                index="name"
                categories={["Findings"]}
                colors={["teal"]}
                layout="vertical"
                yAxisWidth={96}
                showLegend={false}
                showAnimation
                className="h-52"
              />
            )}
          </ChartCard>
          <ChartCard title="Signals by type" description="Distribution across the taxonomy">
            {overview.isLoading ? (
              <Skeleton className="h-44 w-full" />
            ) : donutData.length === 0 ? (
              <p className="py-10 text-center text-sm text-muted-foreground">No data</p>
            ) : (
              <DonutChart
                data={donutData}
                category="value"
                index="name"
                colors={donutColors}
                showAnimation
                className="h-44"
              />
            )}
          </ChartCard>

          <Card>
            <CardHeader className="flex-row items-center justify-between space-y-0 pb-3">
              <CardTitle className="text-base">Competitors</CardTitle>
              <Link href="/competitors" className="text-sm text-primary hover:underline">
                View all
              </Link>
            </CardHeader>
            <CardContent className="pt-0">
              <AsyncState
                isLoading={competitors.isLoading}
                isError={competitors.isError}
                error={competitors.error}
                onRetry={() => competitors.refetch()}
                isEmpty={(competitors.data?.length ?? 0) === 0}
                skeleton={
                  <div className="flex flex-col gap-2">
                    {Array.from({ length: 4 }).map((_, i) => (
                      <Skeleton key={i} className="h-10 w-full" />
                    ))}
                  </div>
                }
                empty={
                  <EmptyState
                    icon={Building2}
                    title="No competitors"
                    description="Add your first competitor in Settings."
                  />
                }
              >
                <ul className="flex flex-col">
                  {competitors.data?.map((c) => (
                    <li key={c.id}>
                      <Link
                        href={`/competitors/${c.id}`}
                        className="flex items-center gap-3 rounded-md px-2 py-2 transition-colors hover:bg-secondary/50"
                      >
                        <CompetitorAvatar name={c.name} id={c.id} size="sm" />
                        <span className="min-w-0 flex-1">
                          <span className="block truncate text-sm font-medium">{c.name}</span>
                          <span className="block text-xs text-muted-foreground">
                            {c.industry ?? c.domain ?? "-"}
                          </span>
                        </span>
                        <span className="tabular text-sm text-muted-foreground">
                          {c.signal_count}
                        </span>
                      </Link>
                    </li>
                  ))}
                </ul>
              </AsyncState>
            </CardContent>
          </Card>
        </div>
      </div>

      {/* Weekly trend */}
      <div className="mt-6">
        <ChartCard
          title="Weekly activity"
          description="Detected changes per week, with high-significance overlay"
          action={<Activity className="h-4 w-4 text-muted-foreground" />}
        >
          {overview.isLoading ? (
            <Skeleton className="h-72 w-full" />
          ) : (
            <AreaChart
              data={trend}
              index="week"
              categories={["total_changes", "high_significance_changes"]}
              colors={["teal", "amber"]}
              showAnimation
              showLegend
              yAxisWidth={36}
              className="h-72"
            />
          )}
        </ChartCard>
      </div>
    </div>
  );
}
