"use client";

// Activity tracker: what the system is doing, what happened, where it went.
// One React context + reducer (no state library), persisted to localStorage.
// API calls are instrumented once, centrally, by wrapping window.fetch for
// same-origin /api requests. Labels only - never keys, bodies or full payloads.

import { usePathname } from "next/navigation";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useReducer,
  useRef,
  type ReactNode,
} from "react";

export type ActivityKind = "api" | "nav" | "action" | "stage";
export type ActivityStatus = "pending" | "success" | "error" | "info";

export interface ActivityEntry {
  id: string;
  kind: ActivityKind;
  label: string;
  status: ActivityStatus;
  at: number;
  durationMs?: number;
  error?: string;
  route?: string;
}

type Action =
  | { type: "add"; entry: ActivityEntry }
  | { type: "update"; id: string; patch: Partial<ActivityEntry> }
  | { type: "clear" }
  | { type: "seen" };

interface State {
  entries: ActivityEntry[];
  seenAt: number;
}

const MAX = 100;
const STORE_KEY = "mi-activity-v1";

export function activityReducer(state: State, action: Action): State {
  switch (action.type) {
    case "add":
      return { ...state, entries: [...state.entries, action.entry].slice(-MAX) };
    case "update":
      return {
        ...state,
        entries: state.entries.map((e) => (e.id === action.id ? { ...e, ...action.patch } : e)),
      };
    case "clear":
      return { entries: [], seenAt: Date.now() };
    case "seen":
      return { ...state, seenAt: Date.now() };
  }
}

/** Human label for an API call. Pure: covered by tsc; no payload is inspected. */
export function labelFor(method: string, path: string): { label: string; route?: string } | null {
  const p = path.replace(/^\/api/, "").split("?")[0];
  const m = method.toUpperCase();
  const id = (re: RegExp) => decodeURIComponent(p.match(re)?.[1] ?? "");
  if (m === "POST" && p === "/research") return { label: "Started a research run", route: "/research" };
  if (m === "POST" && /^\/companies\/[^/]+\/refresh$/.test(p)) {
    const c = id(/^\/companies\/([^/]+)/);
    return { label: `Refreshing news for ${prettyId(c)}`, route: `/competitors/${c}` };
  }
  if (m === "PUT" && p === "/settings/llm") return { label: "Saved AI summary settings" };
  if (m === "POST" && p === "/settings/llm/test") return { label: "Tested the LLM connection" };
  if (m === "POST" && p === "/pipeline/run") return { label: "Started the extraction pipeline" };
  if (m === "POST" && p === "/competitors") return { label: "Added a company", route: "/competitors" };
  if (m === "PATCH" && p.startsWith("/competitors/")) return { label: "Updated a company", route: "/settings" };
  if (m === "DELETE" && p.startsWith("/competitors/")) return { label: "Removed a company", route: "/settings" };
  if (m === "POST" && p === "/assistant/chat") return null; // the guide shows its own state
  if (m !== "GET") return { label: `${m} ${p}` };
  // Reads: only log the meaningful ones, and never polling of a single run.
  if (p === "/findings") return { label: "Loaded intelligence feed", route: "/feed" };
  if (p === "/stats/overview") return { label: "Loaded overview", route: "/dashboard" };
  if (/^\/research\/[^/]+\/sources$/.test(p)) return { label: "Loaded report sources" };
  if (/^\/companies\/[^/]+\/developments$/.test(p)) return { label: "Loaded live developments" };
  return null;
}

const ACRONYMS = new Set(["tvs", "ev", "mg", "bmw", "byd", "abb", "lg", "tcs", "hcl"]);

function prettyId(slug: string): string {
  return slug
    .split("-")
    .map((w) => (ACRONYMS.has(w.toLowerCase()) ? w.toUpperCase() : w.charAt(0).toUpperCase() + w.slice(1)))
    .join(" ");
}

const PAGE_LABELS: [RegExp, (m: RegExpMatchArray) => string][] = [
  [/^\/dashboard/, () => "Overview"],
  [/^\/research\/view/, () => "Research report"],
  [/^\/research/, () => "Research"],
  [/^\/feed/, () => "Feed"],
  [/^\/competitors\/([^/]+)/, (m) => `Companies → ${prettyId(m[1])}`],
  [/^\/competitors/, () => "Companies"],
  [/^\/signals/, () => "Signals"],
  [/^\/changes/, () => "Changes"],
  [/^\/reports/, () => "Reports"],
  [/^\/settings/, () => "Settings"],
];

export function pageLabel(pathname: string): string {
  for (const [re, f] of PAGE_LABELS) {
    const m = pathname.match(re);
    if (m) return f(m);
  }
  return pathname;
}

interface Ctx {
  entries: ActivityEntry[];
  unseenErrors: number;
  running: number;
  log: (e: Omit<ActivityEntry, "id" | "at" | "status"> & { status?: ActivityStatus }) => string;
  update: (id: string, patch: Partial<ActivityEntry>) => void;
  clear: () => void;
  markSeen: () => void;
}

const ActivityContext = createContext<Ctx | null>(null);

let counter = 0;
const newId = () => `${Date.now().toString(36)}-${(counter++).toString(36)}`;

function load(): State {
  try {
    const raw = localStorage.getItem(STORE_KEY);
    if (raw) {
      const s = JSON.parse(raw) as State;
      // Anything still "pending" from a previous visit can't be finished now.
      s.entries = (s.entries ?? []).map((e) => (e.status === "pending" ? { ...e, status: "info" } : e));
      return { entries: s.entries.slice(-MAX), seenAt: s.seenAt ?? 0 };
    }
  } catch {
    /* storage unavailable */
  }
  return { entries: [], seenAt: Date.now() };
}

export function ActivityProvider({ children }: { children: ReactNode }) {
  const [state, dispatch] = useReducer(activityReducer, { entries: [], seenAt: 0 });
  const loaded = useRef(false);

  useEffect(() => {
    const s = load();
    s.entries.forEach((entry) => dispatch({ type: "add", entry }));
    loaded.current = true;
  }, []);

  useEffect(() => {
    if (!loaded.current) return;
    try {
      localStorage.setItem(STORE_KEY, JSON.stringify(state));
    } catch {
      /* ignore */
    }
  }, [state]);

  const log = useCallback<Ctx["log"]>((e) => {
    const id = newId();
    dispatch({ type: "add", entry: { status: "info", ...e, id, at: Date.now() } });
    return id;
  }, []);
  const update = useCallback((id: string, patch: Partial<ActivityEntry>) => dispatch({ type: "update", id, patch }), []);

  // Central API instrumentation (same-origin /api only).
  useEffect(() => {
    const orig = window.fetch;
    const wrapped: typeof fetch = async (input, init) => {
      const url = typeof input === "string" ? input : input instanceof URL ? input.toString() : input.url;
      const path = url.startsWith("/") ? url : url.replace(window.location.origin, "");
      const lbl = path.startsWith("/api") ? labelFor(init?.method ?? "GET", path) : null;
      if (!lbl) return orig(input, init);
      const id = newId();
      const t0 = performance.now();
      dispatch({ type: "add", entry: { id, kind: "api", status: "pending", at: Date.now(), ...lbl } });
      try {
        const res = await orig(input, init);
        dispatch({
          type: "update",
          id,
          patch: {
            status: res.ok ? "success" : "error",
            durationMs: Math.round(performance.now() - t0),
            error: res.ok ? undefined : `Request failed (${res.status})`,
          },
        });
        return res;
      } catch (err) {
        dispatch({
          type: "update",
          id,
          patch: {
            status: "error",
            durationMs: Math.round(performance.now() - t0),
            error: err instanceof DOMException && err.name === "AbortError" ? "Cancelled" : "Network error",
          },
        });
        throw err;
      }
    };
    window.fetch = wrapped;
    return () => {
      window.fetch = orig;
    };
  }, []);

  // Navigation.
  const pathname = usePathname();
  const lastPath = useRef<string | null>(null);
  useEffect(() => {
    if (!pathname || pathname === lastPath.current) return;
    if (lastPath.current !== null) log({ kind: "nav", label: `Opened ${pageLabel(pathname)}`, route: pathname });
    lastPath.current = pathname;
  }, [pathname, log]);

  const value = useMemo<Ctx>(
    () => ({
      entries: state.entries,
      unseenErrors: state.entries.filter((e) => e.status === "error" && e.at > state.seenAt).length,
      running: state.entries.filter((e) => e.status === "pending").length,
      log,
      update,
      clear: () => dispatch({ type: "clear" }),
      markSeen: () => dispatch({ type: "seen" }),
    }),
    [state, log, update],
  );

  return <ActivityContext.Provider value={value}>{children}</ActivityContext.Provider>;
}

const noop: Ctx = {
  entries: [],
  unseenErrors: 0,
  running: 0,
  log: () => "",
  update: () => undefined,
  clear: () => undefined,
  markSeen: () => undefined,
};

export function useActivity(): Ctx {
  return useContext(ActivityContext) ?? noop;
}
