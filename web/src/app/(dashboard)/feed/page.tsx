"use client";

import { Inbox } from "lucide-react";
import { useState } from "react";

import { AsyncState } from "@/components/async-state";
import { EmptyState } from "@/components/empty-state";
import { PageHeader } from "@/components/page-header";
import { FindingCard } from "@/components/research/research-ui";
import { Skeleton } from "@/components/ui/skeleton";
import { useFindingsFeed } from "@/lib/research-api";
import {
  CATEGORY_LABEL,
  FINDING_CATEGORIES,
  KIND_LABEL,
  type FindingCategory,
  type FindingKind,
} from "@/lib/research-types";
import { cn } from "@/lib/utils";

export default function FeedPage() {
  const [category, setCategory] = useState<FindingCategory | undefined>();
  const [kind, setKind] = useState<FindingKind | undefined>();
  const [includeDemo, setIncludeDemo] = useState(true);
  const feed = useFindingsFeed({ category, kind, include_demo: includeDemo, limit: 200 });

  const chip = (active: boolean) =>
    cn(
      "rounded-full border px-3 py-1 text-xs font-medium transition-colors",
      active ? "border-primary bg-primary/15 text-foreground" : "text-muted-foreground hover:bg-secondary",
    );

  return (
    <div>
      <PageHeader
        title="Intelligence feed"
        description="Structured findings from every research run, newest first."
      />

      <div className="mb-4 flex flex-col gap-3">
        <div className="flex flex-wrap gap-2">
          <button className={chip(!category)} onClick={() => setCategory(undefined)}>
            All categories
          </button>
          {FINDING_CATEGORIES.map((c) => (
            <button key={c} className={chip(category === c)} onClick={() => setCategory(c)}>
              {CATEGORY_LABEL[c]}
            </button>
          ))}
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <button className={chip(!kind)} onClick={() => setKind(undefined)}>
            All kinds
          </button>
          {(Object.keys(KIND_LABEL) as FindingKind[]).map((k) => (
            <button key={k} className={chip(kind === k)} onClick={() => setKind(k)}>
              {KIND_LABEL[k]}
            </button>
          ))}
          <label className="ml-auto flex items-center gap-2 text-xs text-muted-foreground">
            <input type="checkbox" checked={includeDemo} onChange={(e) => setIncludeDemo(e.target.checked)} />
            Include demo snapshot
          </label>
        </div>
      </div>

      <AsyncState
        isLoading={feed.isLoading}
        isError={feed.isError}
        error={feed.error}
        onRetry={() => feed.refetch()}
        isEmpty={(feed.data?.items.length ?? 0) === 0}
        skeleton={
          <div className="flex flex-col gap-3">
            {Array.from({ length: 5 }).map((_, i) => (
              <Skeleton key={i} className="h-28 w-full" />
            ))}
          </div>
        }
        empty={
          <EmptyState
            icon={Inbox}
            title="No findings match"
            description="Run research from the Research workspace, or relax the filters."
          />
        }
      >
        <p className="mb-2 text-xs text-muted-foreground">{feed.data?.total} findings</p>
        <div className="flex flex-col gap-3">
          {feed.data?.items.map((f) => <FindingCard key={f.id} finding={f} showRun />)}
        </div>
      </AsyncState>
    </div>
  );
}
