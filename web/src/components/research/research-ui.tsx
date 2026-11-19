"use client";

import {
  AlertTriangle,
  CheckCircle2,
  CircleDashed,
  ExternalLink,
  FlaskConical,
  Loader2,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import Link from "next/link";

import { RelativeTime } from "@/components/relative-time";
import { SignificanceDots } from "@/components/significance";
import { Badge } from "@/components/ui/badge";
import {
  CATEGORY_LABEL,
  type FeedFinding,
  type FindingCategory,
  type ResearchFinding,
  type ResearchRunSummary,
  type ResearchSource,
  type ResearchStatus,
} from "@/lib/research-types";
import { cn } from "@/lib/utils";

const STATUS: Record<ResearchStatus, { label: string; cls: string; icon: typeof Loader2; spin?: boolean }> = {
  queued: { label: "Queued", cls: "bg-muted text-muted-foreground", icon: CircleDashed },
  running: { label: "Researching", cls: "bg-sky-500/15 text-sky-600 dark:text-sky-400", icon: Loader2, spin: true },
  completed: { label: "Completed", cls: "bg-emerald-500/15 text-emerald-700 dark:text-emerald-400", icon: CheckCircle2 },
  partial: { label: "Partial", cls: "bg-amber-500/15 text-amber-700 dark:text-amber-400", icon: AlertTriangle },
  failed: { label: "Failed", cls: "bg-destructive/15 text-destructive", icon: AlertTriangle },
};

export function StatusBadge({ status }: { status: ResearchStatus }) {
  const s = STATUS[status] ?? STATUS.queued;
  const Icon = s.icon;
  return (
    <Badge variant="muted" className={cn("border-transparent", s.cls)}>
      <Icon className={cn("h-3 w-3", s.spin && "animate-spin")} />
      {s.label}
    </Badge>
  );
}

export function DataOriginBadge({ isDemo, provider }: { isDemo: boolean; provider?: string | null }) {
  return isDemo ? (
    <Badge variant="outline" className="border-amber-500/40 text-amber-700 dark:text-amber-400">
      <FlaskConical className="h-3 w-3" /> Demo snapshot
    </Badge>
  ) : (
    <Badge variant="outline" className="border-emerald-500/40 text-emerald-700 dark:text-emerald-400">
      <Sparkles className="h-3 w-3" /> Live · {provider ?? "provider"}
    </Badge>
  );
}

const CAT_CLS: Record<FindingCategory, string> = {
  expansion: "bg-violet-500/15 text-violet-700 dark:text-violet-300",
  product_launch: "bg-lime-500/20 text-lime-800 dark:text-lime-300",
  partnership: "bg-sky-500/15 text-sky-700 dark:text-sky-300",
  funding: "bg-emerald-500/15 text-emerald-700 dark:text-emerald-300",
  policy: "bg-orange-500/15 text-orange-700 dark:text-orange-300",
  tender: "bg-rose-500/15 text-rose-700 dark:text-rose-300",
  hiring: "bg-teal-500/15 text-teal-700 dark:text-teal-300",
  technology: "bg-indigo-500/15 text-indigo-700 dark:text-indigo-300",
  market_entry: "bg-fuchsia-500/15 text-fuchsia-700 dark:text-fuchsia-300",
  other: "bg-muted text-muted-foreground",
};

export function CategoryBadge({ category }: { category: FindingCategory }) {
  return (
    <Badge variant="muted" className={cn("border-transparent", CAT_CLS[category] ?? CAT_CLS.other)}>
      {CATEGORY_LABEL[category] ?? category}
    </Badge>
  );
}

export function KindBadge({ kind, flags }: { kind: ResearchFinding["kind"]; flags: string[] }) {
  if (kind === "verified_fact")
    return (
      <Badge variant="outline" className="border-emerald-500/40 text-emerald-700 dark:text-emerald-400">
        <ShieldCheck className="h-3 w-3" /> Provider-cited fact
      </Badge>
    );
  const unverified = flags.includes("unverified_citation") || flags.includes("dead_citation");
  return (
    <Badge variant="outline" className="text-muted-foreground" title={unverified ? "The provider labelled this a fact, but its cited link was missing or unreachable" : undefined}>
      Analysis{unverified ? " · citation unverified" : ""}
    </Badge>
  );
}

export function FindingCard({
  finding,
  sources,
  showRun,
}: {
  finding: ResearchFinding | FeedFinding;
  sources?: Map<string, ResearchSource>;
  showRun?: boolean;
}) {
  const feed = finding as FeedFinding;
  const cited = (finding.source_ids ?? []).map((id) => sources?.get(id)).filter(Boolean) as ResearchSource[];
  return (
    <div className="rounded-lg border bg-card p-4 transition-colors hover:bg-secondary/30">
      <div className="flex flex-wrap items-center gap-2">
        <CategoryBadge category={finding.category} />
        <KindBadge kind={finding.kind} flags={finding.flags} />
        {showRun && feed.is_demo && <DataOriginBadge isDemo />}
        {finding.entity && <span className="text-sm font-medium">{finding.entity}</span>}
        <span className="ml-auto flex items-center gap-2">
          <SignificanceDots value={finding.significance} />
          {finding.event_date && (
            <span className="text-xs text-muted-foreground">{finding.event_date}</span>
          )}
        </span>
      </div>
      <p className="mt-2 text-sm font-semibold">{finding.title}</p>
      {finding.summary && <p className="mt-1 text-sm text-muted-foreground">{finding.summary}</p>}
      <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground">
        {finding.confidence != null && <span>Confidence {Math.round(finding.confidence * 100)}%</span>}
        {cited.map((s) => (
          <a
            key={s.id}
            href={s.url}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1 text-primary hover:underline"
          >
            <ExternalLink className="h-3 w-3" />
            {s.domain ?? s.url}
          </a>
        ))}
        {!sources && finding.source_ids.length > 0 && (
          <span>{finding.source_ids.length} linked source(s)</span>
        )}
        {showRun && (
          <Link href={`/research/view?id=${encodeURIComponent(finding.research_run_id)}`} className="ml-auto text-primary hover:underline">
            Open report
          </Link>
        )}
      </div>
    </div>
  );
}

export function RunRow({ run }: { run: ResearchRunSummary }) {
  return (
    <Link
      href={`/research/view?id=${encodeURIComponent(run.id)}`}
      className="flex flex-col gap-1.5 rounded-lg border bg-card p-3 transition-colors hover:bg-secondary/40"
    >
      <div className="flex flex-wrap items-center gap-2">
        <StatusBadge status={run.status} />
        <DataOriginBadge isDemo={run.is_demo} provider={run.provider} />
        <RelativeTime value={run.created_at} className="ml-auto text-xs" />
      </div>
      <p className="line-clamp-2 text-sm font-medium">{run.objective}</p>
      <p className="text-xs text-muted-foreground">
        {[run.industry, run.geography].filter(Boolean).join(" · ")}
        {(run.status === "completed" || run.status === "partial") &&
          ` · ${run.finding_count} findings · ${run.source_count} sources`}
        {run.status === "failed" && run.error_message && ` · ${run.error_message}`}
      </p>
    </Link>
  );
}
