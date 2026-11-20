"use client";

import { useIsFetching, useIsMutating } from "@tanstack/react-query";
import { AnimatePresence, motion, useScroll, useSpring } from "framer-motion";
import {
  Activity as ActivityIcon,
  AlertTriangle,
  CheckCircle2,
  CircleDot,
  Compass,
  Info,
  Loader2,
  MousePointerClick,
  Workflow,
  X,
} from "lucide-react";
import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import { type ActivityEntry, useActivity } from "@/lib/activity";
import { cn } from "@/lib/utils";

// ------------------------------------------------------------ activity bar --
function ActivityBarInner() {
  const fetching = useIsFetching();
  const mutating = useIsMutating();
  const pathname = usePathname();
  const search = useSearchParams();
  const [routing, setRouting] = useState(false);
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);

  useEffect(() => {
    setRouting(true);
    const t = setTimeout(() => setRouting(false), 450);
    return () => clearTimeout(t);
  }, [pathname, search]);

  // Client-only: in-flight counts differ between server render and hydration.
  const busy = mounted && (fetching + mutating > 0 || routing);
  return (
    <AnimatePresence>
      {busy && (
        <motion.div
          key="bar"
          aria-hidden
          className="pointer-events-none fixed inset-x-0 top-0 z-[60] h-0.5 origin-left bg-gradient-to-r from-primary via-primary to-accent"
          initial={{ scaleX: 0, opacity: 1 }}
          animate={{ scaleX: [0, 0.55, 0.85], opacity: 1 }}
          exit={{ scaleX: 1, opacity: 0, transition: { duration: 0.35 } }}
          transition={{ duration: 1.6, ease: [0.16, 1, 0.3, 1] }}
        />
      )}
    </AnimatePresence>
  );
}

/** 2px bar at the very top while any query, mutation or route change is in flight. */
export function ActivityBar() {
  return (
    <Suspense fallback={null}>
      <ActivityBarInner />
    </Suspense>
  );
}

// -------------------------------------------------------- reading progress --
/** Thin bar under the header on long pages, driven by scroll position. */
export function ReadingProgress() {
  const { scrollYProgress } = useScroll();
  const scaleX = useSpring(scrollYProgress, { stiffness: 220, damping: 32, mass: 0.3 });
  const pathname = usePathname();
  const [scrollable, setScrollable] = useState(false);

  useEffect(() => {
    const check = () => setScrollable(document.documentElement.scrollHeight > window.innerHeight * 1.4);
    check();
    const ro = new ResizeObserver(check);
    ro.observe(document.body);
    return () => ro.disconnect();
  }, [pathname]);

  if (!scrollable) return null;
  return (
    <motion.div
      aria-hidden
      className="absolute inset-x-0 bottom-0 h-px origin-left bg-primary/70"
      style={{ scaleX }}
    />
  );
}

// ---------------------------------------------------------- activity drawer --
const KIND_ICON = { api: Workflow, nav: Compass, action: MousePointerClick, stage: CircleDot } as const;

function StatusIcon({ e }: { e: ActivityEntry }) {
  if (e.status === "pending") return <Loader2 className="h-4 w-4 animate-spin text-primary" />;
  if (e.status === "error") return <AlertTriangle className="h-4 w-4 text-destructive" />;
  if (e.status === "success") return <CheckCircle2 className="h-4 w-4 text-primary" />;
  const Icon = KIND_ICON[e.kind] ?? Info;
  return <Icon className="h-4 w-4 text-muted-foreground" />;
}

function ago(ts: number): string {
  const s = Math.max(1, Math.round((Date.now() - ts) / 1000));
  if (s < 60) return `${s}s ago`;
  const m = Math.round(s / 60);
  if (m < 60) return `${m}m ago`;
  return `${Math.round(m / 60)}h ago`;
}

export function ActivityButton({ onClick }: { onClick: () => void }) {
  const { running, unseenErrors } = useActivity();
  return (
    <button
      type="button"
      onClick={onClick}
      aria-label={`Activity${running ? `, ${running} running` : ""}${unseenErrors ? `, ${unseenErrors} failed` : ""}`}
      className="pressable relative flex h-9 w-9 items-center justify-center rounded-lg border bg-card/70 text-muted-foreground hover:text-foreground"
    >
      <ActivityIcon className="h-4 w-4" />
      {running > 0 && (
        <span className="absolute right-1.5 top-1.5 flex h-2 w-2">
          <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-primary opacity-60" />
          <span className="relative inline-flex h-2 w-2 rounded-full bg-primary" />
        </span>
      )}
      {unseenErrors > 0 && (
        <span className="absolute -right-1 -top-1 flex h-4 min-w-4 items-center justify-center rounded-full bg-destructive px-1 text-[10px] font-semibold text-destructive-foreground">
          {unseenErrors}
        </span>
      )}
    </button>
  );
}

type Filter = "all" | "running" | "errors";

export function ActivityDrawer({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { entries, clear, markSeen } = useActivity();
  const [filter, setFilter] = useState<Filter>("all");
  const [, tick] = useState(0);

  useEffect(() => {
    if (!open) return;
    markSeen();
    const t = setInterval(() => tick((n) => n + 1), 15000);
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => {
      clearInterval(t);
      window.removeEventListener("keydown", onKey);
    };
  }, [open]); // eslint-disable-line react-hooks/exhaustive-deps

  const groups = useMemo(() => {
    const list = [...entries]
      .reverse()
      .filter((e) => (filter === "running" ? e.status === "pending" : filter === "errors" ? e.status === "error" : true));
    const cut = Date.now() - 10 * 60 * 1000;
    return [
      { title: "Now", items: list.filter((e) => e.at >= cut || e.status === "pending") },
      { title: "Earlier", items: list.filter((e) => e.at < cut && e.status !== "pending") },
    ].filter((g) => g.items.length);
  }, [entries, filter]);

  return (
    <AnimatePresence>
      {open && (
        <>
          <motion.div
            className="fixed inset-0 z-40 bg-foreground/20 backdrop-blur-[2px]"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
          />
          <motion.aside
            role="dialog"
            aria-modal="true"
            aria-label="Activity"
            className="fixed inset-y-0 right-0 z-50 flex w-full max-w-sm flex-col border-l bg-card shadow-2xl"
            initial={{ x: "100%" }}
            animate={{ x: 0 }}
            exit={{ x: "100%" }}
            transition={{ type: "spring", stiffness: 380, damping: 40 }}
          >
            <div className="flex items-center justify-between border-b p-4">
              <div>
                <h2 className="text-lg font-semibold">Activity</h2>
                <p className="text-xs text-muted-foreground">What the app did, in order. Stored in this browser only.</p>
              </div>
              <Button variant="ghost" size="icon" onClick={onClose} aria-label="Close activity">
                <X className="h-4 w-4" />
              </Button>
            </div>
            <div className="flex items-center gap-1.5 border-b px-4 py-2">
              {(["all", "running", "errors"] as Filter[]).map((f) => (
                <button
                  key={f}
                  type="button"
                  onClick={() => setFilter(f)}
                  className={cn(
                    "rounded-full border px-3 py-1 text-xs capitalize transition-colors",
                    filter === f ? "border-primary bg-primary/15 text-foreground" : "text-muted-foreground hover:bg-secondary",
                  )}
                >
                  {f}
                </button>
              ))}
              <button type="button" onClick={clear} className="ml-auto text-xs text-muted-foreground hover:text-foreground">
                Clear
              </button>
            </div>
            <div className="flex-1 overflow-y-auto p-3">
              {groups.length === 0 && (
                <p className="px-2 py-10 text-center text-sm text-muted-foreground">
                  Nothing here yet. Actions like running research or refreshing news show up as they happen.
                </p>
              )}
              {groups.map((g) => (
                <div key={g.title} className="mb-4">
                  <h3 className="mb-1 px-2 text-xs font-medium text-muted-foreground">{g.title}</h3>
                  <ul>
                    <AnimatePresence initial={false}>
                      {g.items.map((e) => {
                        const row = (
                          <span className="flex items-start gap-2.5">
                            <span className="mt-0.5">
                              <StatusIcon e={e} />
                            </span>
                            <span className="min-w-0 flex-1">
                              <span className="block text-sm">{e.label}</span>
                              <span className="block text-[11px] text-muted-foreground">
                                {ago(e.at)}
                                {e.durationMs != null && ` · ${(e.durationMs / 1000).toFixed(1)}s`}
                                {e.error && <span className="text-destructive"> · {e.error}</span>}
                              </span>
                            </span>
                          </span>
                        );
                        return (
                          <motion.li
                            key={e.id}
                            layout
                            initial={{ opacity: 0, y: -4 }}
                            animate={{ opacity: 1, y: 0 }}
                            exit={{ opacity: 0 }}
                            className={cn(
                              "rounded-lg border-l-2 px-2 py-2",
                              e.status === "error" ? "border-destructive" : e.status === "pending" ? "border-primary" : "border-transparent",
                            )}
                          >
                            {e.route ? (
                              <Link href={e.route} onClick={onClose} className="block rounded hover:bg-secondary/60">
                                {row}
                              </Link>
                            ) : (
                              row
                            )}
                          </motion.li>
                        );
                      })}
                    </AnimatePresence>
                  </ul>
                </div>
              ))}
            </div>
          </motion.aside>
        </>
      )}
    </AnimatePresence>
  );
}
