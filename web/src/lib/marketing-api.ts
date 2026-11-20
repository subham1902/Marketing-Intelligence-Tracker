"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef } from "react";
import { toast } from "sonner";

import { useActivity } from "./activity";

const BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "/api";

export type Ev = { quote: string; evidence_id: string; date?: string | null; label?: string };
export type EvidenceItem = {
  id: string;
  url: string;
  domain: string;
  title?: string | null;
  date?: string | null;
  fetched: boolean;
  aggregator?: boolean;
};
export type Rated = { evidence: Ev[]; label: string };
export type MarketingResult = {
  snapshot: {
    summary: string;
    sector?: string | null;
    evidence_count: number;
    fetched_count: number;
    coverage: Record<string, number>;
  };
  profitability: {
    figures: { metric: string; value: string; period?: string | null; quote: string; evidence_id: string }[];
    trend?: string | null;
    label: string;
    summary: string;
    how: string;
  };
  moat: (Rated & { dimension: string; rating: string })[];
  stakeholders: (Rated & { name: string; power: string; interest: string; mentions: number })[];
  porter: { force: string; level: string; reason: string; how: string; evidence: Ev[] }[];
  competition: { id: string; name: string; co_mentions: number; doing: Ev[]; segment?: string | null }[];
  tone: {
    score: number | null;
    n: number;
    label?: string;
    trend: { period: string; score: number; n: number }[];
    most_positive: Ev | null;
    most_negative: Ev | null;
  };
  need_gaps: (Rated & { gap: string; why: string })[];
  segmentation: (Rated & { segment: string })[];
  positioning: {
    past: Ev[];
    present: Ev[];
    future: Ev[];
    forecast?: string | null;
    map: { x_axis: string; y_axis: string; how: string; points: { name: string; self: boolean; x: number; y: number }[] };
  };
  gtm: { timeline: Ev[]; future: Ev[]; forecast?: string | null };
  mix: (Rated & { p: string; rating: string; cues: number })[];
  recommendations: {
    priority: number;
    action: string;
    why: string;
    impact?: string;
    effort?: string;
    kpi?: string;
    label: string;
    evidence_ids?: string[];
  }[];
  ai_insights?: { claim: string; evidence_ids: string[]; quote: string | null; label: string }[];
};
export type Analysis = {
  id: string;
  company: string;
  company_name?: string;
  mode?: string | null;
  status: "queued" | "running" | "completed" | "failed";
  stage?: string | null;
  error?: string | null;
  is_snapshot?: boolean;
  created_at: string;
  completed_at?: string | null;
  result?: MarketingResult;
  evidence?: EvidenceItem[];
};

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, { ...init, headers: { "Content-Type": "application/json" } });
  if (!res.ok) {
    let m = `Request failed (${res.status})`;
    try {
      const b = await res.json();
      m = b?.error?.message ?? m;
    } catch {
      /* ignore */
    }
    throw new Error(m);
  }
  return res.json() as Promise<T>;
}

export const useAnalyses = (company?: string) =>
  useQuery({
    queryKey: ["marketing", "list", company ?? ""],
    queryFn: () => req<Analysis[]>(`/marketing/analyses${company ? `?company=${encodeURIComponent(company)}` : ""}`),
  });

export const useAnalysis = (id?: string) =>
  useQuery({
    queryKey: ["marketing", "one", id],
    queryFn: () => req<Analysis>(`/marketing/analyses/${encodeURIComponent(id!)}`),
    enabled: !!id,
    refetchInterval: (q) => {
      const s = q.state.data?.status;
      return s === "queued" || s === "running" ? 2000 : false;
    },
    refetchIntervalInBackground: true,
  });

export function useStartAnalysis() {
  const qc = useQueryClient();
  const { log } = useActivity();
  return useMutation({
    mutationFn: (body: { company?: string; name?: string }) =>
      req<Analysis>("/marketing/analyses", { method: "POST", body: JSON.stringify(body) }),
    onSuccess: (a) => {
      log({ kind: "action", label: `Marketing analysis started: ${a.company_name ?? a.company}`, route: "/marketing" });
      qc.invalidateQueries({ queryKey: ["marketing", "list"] });
    },
    onError: (e: Error) => toast.error(e.message),
  });
}

/** Log stage changes and completion of a running analysis to the Activity drawer. */
export function useAnalysisActivity(a?: Analysis) {
  const { log } = useActivity();
  const last = useRef<string>("");
  useEffect(() => {
    if (!a || a.is_snapshot) return;
    const key = `${a.id}:${a.status}:${a.stage}`;
    if (key === last.current) return;
    const first = last.current === "";
    last.current = key;
    if (first && a.status === "completed") return;
    if (a.status === "running" && a.stage) log({ kind: "stage", label: `Marketing: ${a.stage}`, route: "/marketing" });
    if (a.status === "completed") {
      log({ kind: "stage", label: `Marketing analysis ready: ${a.company_name}`, route: "/marketing" });
      toast.success(`Marketing analysis ready: ${a.company_name}`);
    }
    if (a.status === "failed") toast.error(a.error ?? "Analysis failed");
  }, [a, log]);
}
