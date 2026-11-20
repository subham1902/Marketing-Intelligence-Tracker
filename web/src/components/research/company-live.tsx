"use client";

import { Loader2, Newspaper, RefreshCw } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";

import { EmptyState } from "@/components/empty-state";
import { FindingCard, StageBar, StatusBadge } from "@/components/research/research-ui";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useCompanyDevelopments, useRefreshCompany, useResearchRun } from "@/lib/research-api";

/** Live developments from free public sources, kept apart from [Sample] seed signals. */
export function CompanyLiveDevelopments({ id }: { id: string }) {
  const dev = useCompanyDevelopments(id);
  const refresh = useRefreshCompany(id);
  const [runId, setRunId] = useState<string>("");
  const run = useResearchRun(runId);
  const qc = useQueryClient();
  const active = run.data && (run.data.status === "queued" || run.data.status === "running");

  useEffect(() => {
    if (run.data && !active) qc.invalidateQueries({ queryKey: ["company-developments", id] });
  }, [run.data?.status]); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <Card className="mt-6">
      <CardHeader className="flex-row items-center justify-between space-y-0 pb-3">
        <CardTitle className="flex items-center gap-2 text-base">
          <Newspaper className="h-4 w-4 text-muted-foreground" /> Live developments
          <span className="text-xs font-normal text-muted-foreground">(from free public sources)</span>
        </CardTitle>
        <Button
          size="sm"
          variant="outline"
          disabled={refresh.isPending || !!active}
          onClick={() => refresh.mutate(undefined, { onSuccess: (r) => setRunId(r.id) })}
        >
          {active ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
          Refresh news
        </Button>
      </CardHeader>
      <CardContent className="pt-0">
        {active && run.data && (
          <div className="mb-3">
            <StageBar status={run.data.status} message={run.data.status_message} compact />
          </div>
        )}
        {run.data && (
          <div className="mb-3 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
            <StatusBadge status={run.data.status} />
            {active && run.data.status_message}
            {run.data.status === "failed" && run.data.error_message}
            <Link href={`/research/view?id=${encodeURIComponent(run.data.id)}`} className="text-primary hover:underline">
              Open run
            </Link>
          </div>
        )}
        {dev.isLoading ? (
          <Skeleton className="h-24 w-full" />
        ) : dev.isError ? (
          <p className="text-sm text-destructive">Couldn&apos;t load live developments.</p>
        ) : (dev.data?.length ?? 0) === 0 ? (
          <EmptyState
            icon={Newspaper}
            title="No live developments yet"
            description="Click Refresh news to search the last month of free public sources for this company."
          />
        ) : (
          <div className="flex flex-col gap-3">
            {dev.data!.slice(0, 8).map((f) => (
              <FindingCard key={f.id} finding={f} showRun />
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
