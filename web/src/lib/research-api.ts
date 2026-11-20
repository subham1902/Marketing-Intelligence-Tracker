"use client";

// Research client + hooks. Live mode talks to FastAPI via the /api proxy.
// Static mode serves the baked snapshot; submitting new research needs the live
// backend, so it fails honestly instead of pretending.

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { ApiError } from "./api";
import type {
  FeedFinding,
  FindingQuery,
  ResearchConfig,
  ResearchCreate,
  ResearchFinding,
  ResearchRun,
  ResearchRunSummary,
  ResearchSource,
} from "./research-types";
import type { Page } from "./types";

const STATIC = process.env.NEXT_PUBLIC_STATIC_DATA === "1";
const BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "/api";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
  });
  if (!res.ok) {
    let message = `Request failed (${res.status})`;
    try {
      const body = await res.json();
      message = body?.error?.message ?? body?.detail ?? message;
    } catch {
      /* non-JSON */
    }
    throw new ApiError(res.status, message);
  }
  return (await res.json()) as T;
}

async function staticGet<T>(file: string, fallback?: T): Promise<T> {
  const res = await fetch(`/api-static/${file}`);
  if (!res.ok) {
    if (fallback !== undefined) return fallback;
    throw new ApiError(res.status, `Missing static data: ${file}`);
  }
  return (await res.json()) as T;
}

function qs(params: object): string {
  const sp = new URLSearchParams();
  for (const [k, v] of Object.entries(params as Record<string, unknown>)) {
    if (v !== undefined && v !== null && v !== "") sp.set(k, String(v));
  }
  const s = sp.toString();
  return s ? `?${s}` : "";
}

const enc = encodeURIComponent;

export const researchApi = {
  config: () =>
    STATIC
      ? Promise.resolve<ResearchConfig>({ provider: "static", live_available: false, mode: "demo" })
      : request<ResearchConfig>("/research/config"),
  runs: () =>
    STATIC
      ? staticGet<ResearchRunSummary[]>("research.json", [])
      : request<ResearchRunSummary[]>("/research"),
  run: (id: string) =>
    STATIC ? staticGet<ResearchRun>(`research/${id}.json`) : request<ResearchRun>(`/research/${enc(id)}`),
  sources: (id: string) =>
    STATIC
      ? staticGet<ResearchSource[]>(`research/${id}/sources.json`, [])
      : request<ResearchSource[]>(`/research/${enc(id)}/sources`),
  findings: (id: string) =>
    STATIC
      ? staticGet<ResearchFinding[]>(`research/${id}/findings.json`, [])
      : request<ResearchFinding[]>(`/research/${enc(id)}/findings`),
  create: (body: ResearchCreate) =>
    STATIC
      ? Promise.reject(new ApiError(503, "Static demo build: live research needs the FastAPI backend."))
      : request<ResearchRun>("/research", { method: "POST", body: JSON.stringify(body) }),
  feed: async (q: FindingQuery = {}): Promise<Page<FeedFinding>> => {
    if (!STATIC) return request<Page<FeedFinding>>(`/findings${qs(q)}`);
    let all = await staticGet<FeedFinding[]>("findings.json", []);
    if (q.category) all = all.filter((f) => f.category === q.category);
    if (q.kind) all = all.filter((f) => f.kind === q.kind);
    if (q.include_demo === false) all = all.filter((f) => !f.is_demo);
    const offset = q.offset ?? 0;
    const limit = q.limit ?? 100;
    return { items: all.slice(offset, offset + limit), total: all.length, limit, offset };
  },
};

const ACTIVE = new Set(["queued", "running"]);

export const researchKeys = {
  config: ["research-config"] as const,
  runs: ["research-runs"] as const,
  run: (id: string) => ["research-run", id] as const,
  sources: (id: string) => ["research-sources", id] as const,
  findings: (id: string) => ["research-findings", id] as const,
  feed: (q: FindingQuery) => ["findings-feed", q] as const,
};

export const useResearchConfig = () =>
  useQuery({ queryKey: researchKeys.config, queryFn: researchApi.config });

export const useResearchRuns = () =>
  useQuery({
    queryKey: researchKeys.runs,
    queryFn: researchApi.runs,
    // Poll only while a run is genuinely in flight on the backend.
    refetchInterval: (q) => (q.state.data?.some((r) => ACTIVE.has(r.status)) ? 3000 : false),
    refetchIntervalInBackground: true,
  });

export const useResearchRun = (id: string) =>
  useQuery({
    queryKey: researchKeys.run(id),
    queryFn: () => researchApi.run(id),
    enabled: !!id,
    refetchInterval: (q) => (q.state.data && ACTIVE.has(q.state.data.status) ? 3000 : false),
    refetchIntervalInBackground: true, // keep status honest if the user switches tabs
  });

export const useResearchSources = (id: string, enabled = true) =>
  useQuery({
    queryKey: researchKeys.sources(id),
    queryFn: () => researchApi.sources(id),
    enabled: !!id && enabled,
  });

export const useResearchFindings = (id: string, enabled = true) =>
  useQuery({
    queryKey: researchKeys.findings(id),
    queryFn: () => researchApi.findings(id),
    enabled: !!id && enabled,
  });

export const useFindingsFeed = (q: FindingQuery = {}) =>
  useQuery({ queryKey: researchKeys.feed(q), queryFn: () => researchApi.feed(q) });

export function useCreateResearch() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: ResearchCreate) => researchApi.create(body),
    onSuccess: (run) => {
      qc.invalidateQueries({ queryKey: researchKeys.runs });
      if (run.status === "failed") {
        toast.error("Research could not start", { description: run.error_message ?? undefined });
      } else {
        toast.success("Research submitted", {
          description: "Status reflects the backend; typical runs take 30-180 seconds.",
        });
      }
    },
    onError: (e) => toast.error(e instanceof Error ? e.message : "Failed to submit research"),
  });
}

// --------------------------- company live news --------------------------- //

export const useCompanyDevelopments = (id: string) =>
  useQuery({
    queryKey: ["company-developments", id] as const,
    queryFn: () =>
      STATIC
        ? Promise.resolve<FeedFinding[]>([])
        : request<FeedFinding[]>(`/companies/${enc(id)}/developments`),
    enabled: !!id,
  });

export function useRefreshCompany(id: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () =>
      STATIC
        ? Promise.reject(new ApiError(503, "Static demo build: refreshing needs the FastAPI backend."))
        : request<ResearchRun>(`/companies/${enc(id)}/refresh`, { method: "POST" }),
    onSuccess: (run) => {
      qc.invalidateQueries({ queryKey: researchKeys.runs });
      if (run.status === "failed") toast.error("Refresh failed", { description: run.error_message ?? undefined });
      else toast.success("Refreshing news", { description: "Searching free public sources for the last month." });
    },
    onError: (e) => toast.error(e instanceof Error ? e.message : "Refresh failed"),
  });
}
