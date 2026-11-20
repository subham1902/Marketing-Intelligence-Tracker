"use client";

import { AnimatePresence, motion } from "framer-motion";
import {
  Bot,
  Building2,
  CornerDownLeft,
  FileText,
  FlaskConical,
  LayoutDashboard,
  Newspaper,
  Search,
  Settings,
} from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";

import { useCompetitors } from "@/lib/hooks";
import { useResearchRuns } from "@/lib/research-api";
import { useActivity } from "@/lib/activity";
import { cn } from "@/lib/utils";

type Item = { id: string; label: string; hint?: string; href: string; icon: typeof Search; guide?: boolean };

const PAGES: Item[] = [
  { id: "p-dash", label: "Overview", href: "/dashboard", icon: LayoutDashboard },
  { id: "p-research", label: "New research", hint: "Ask a market question", href: "/research", icon: FlaskConical },
  { id: "p-feed", label: "Intelligence feed", href: "/feed", icon: Newspaper },
  { id: "p-companies", label: "Companies", href: "/competitors", icon: Building2 },
  { id: "p-reports", label: "Weekly reports", href: "/reports", icon: FileText },
  { id: "p-settings", label: "Settings", href: "/settings", icon: Settings },
];

/** Ctrl/Cmd+K: jump to any page, company or saved research run. */
export function CommandPalette() {
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState("");
  const [active, setActive] = useState(0);
  const router = useRouter();
  const input = useRef<HTMLInputElement>(null);
  const companies = useCompetitors();
  const runs = useResearchRuns();
  const { log } = useActivity();

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setOpen((o) => !o);
      }
      if (e.key === "Escape") setOpen(false);
    };
    const onOpen = () => setOpen(true);
    window.addEventListener("keydown", onKey);
    window.addEventListener("open-command-palette", onOpen);
    return () => {
      window.removeEventListener("keydown", onKey);
      window.removeEventListener("open-command-palette", onOpen);
    };
  }, []);

  useEffect(() => {
    if (open) {
      setQ("");
      setActive(0);
      setTimeout(() => input.current?.focus(), 10);
    }
  }, [open]);

  const items = useMemo(() => {
    const all: Item[] = [
      ...PAGES,
      ...(companies.data ?? []).map((c) => ({
        id: `c-${c.id}`,
        label: c.name,
        hint: "Company",
        href: `/competitors/${c.id}`,
        icon: Building2,
      })),
      ...(companies.data ?? []).map((c) => ({
        id: `m-${c.id}`,
        label: `Marketing analysis: ${c.name}`,
        hint: "Porter, moat, 7P",
        href: `/marketing?company=${encodeURIComponent(c.id)}`,
        icon: FileText,
      })),
      ...(runs.data ?? []).slice(0, 15).map((r) => ({
        id: `r-${r.id}`,
        label: r.objective,
        hint: r.is_demo ? "Demo snapshot" : "Research report",
        href: `/research/view?id=${encodeURIComponent(r.id)}`,
        icon: FileText,
      })),
    ];
    const t = q.trim().toLowerCase();
    const ask: Item = {
      id: "guide",
      label: t ? `Ask the guide: “${q.trim()}”` : "Ask the guide…",
      hint: "Ctrl+/",
      href: "",
      icon: Bot,
      guide: true,
    };
    return [ask, ...(t ? all.filter((i) => `${i.label} ${i.hint ?? ""}`.toLowerCase().includes(t)) : all)].slice(0, 12);
  }, [q, companies.data, runs.data]);

  const go = (i: Item | undefined) => {
    if (!i) return;
    setOpen(false);
    log({ kind: "action", label: `Palette: ${i.label.slice(0, 60)}`, route: i.href || undefined });
    if (i.guide) {
      window.dispatchEvent(new CustomEvent("open-guide", { detail: q.trim() || undefined }));
      return;
    }
    router.push(i.href);
  };

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          className="fixed inset-0 z-50 flex items-start justify-center bg-foreground/20 px-4 pt-[12vh] backdrop-blur-sm"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.15 }}
          onMouseDown={() => setOpen(false)}
        >
          <motion.div
            role="dialog"
            aria-label="Jump to"
            className="w-full max-w-lg overflow-hidden rounded-xl border bg-card shadow-2xl"
            initial={{ opacity: 0, y: -8, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -6, scale: 0.98 }}
            transition={{ duration: 0.18, ease: [0.16, 1, 0.3, 1] }}
            onMouseDown={(e) => e.stopPropagation()}
          >
            <div className="flex items-center gap-2 border-b px-3">
              <Search className="h-4 w-4 text-muted-foreground" />
              <input
                ref={input}
                value={q}
                onChange={(e) => {
                  setQ(e.target.value);
                  setActive(0);
                }}
                onKeyDown={(e) => {
                  if (e.key === "ArrowDown") {
                    e.preventDefault();
                    setActive((a) => Math.min(a + 1, items.length - 1));
                  } else if (e.key === "ArrowUp") {
                    e.preventDefault();
                    setActive((a) => Math.max(a - 1, 0));
                  } else if (e.key === "Enter") {
                    go(items[active]);
                  }
                }}
                placeholder="Jump to a page, company or report…"
                className="h-12 w-full bg-transparent text-sm outline-none placeholder:text-muted-foreground"
              />
            </div>
            <ul className="max-h-80 overflow-y-auto p-1.5">
              {items.length === 0 && (
                <li className="px-3 py-6 text-center text-sm text-muted-foreground">Nothing matches “{q}”.</li>
              )}
              {items.map((i, idx) => {
                const Icon = i.icon;
                return (
                  <li key={i.id}>
                    <button
                      type="button"
                      onMouseEnter={() => setActive(idx)}
                      onClick={() => go(i)}
                      className={cn(
                        "relative flex w-full items-center gap-3 rounded-lg px-3 py-2 text-left text-sm",
                        idx === active ? "text-foreground" : "text-muted-foreground",
                      )}
                    >
                      {idx === active && (
                        <motion.span
                          layoutId="palette-active"
                          className="absolute inset-0 rounded-lg bg-primary/10"
                          transition={{ type: "spring", stiffness: 500, damping: 40 }}
                        />
                      )}
                      <Icon className="relative h-4 w-4 shrink-0" />
                      <span className="relative min-w-0 flex-1 truncate">{i.label}</span>
                      {i.hint && <span className="relative shrink-0 text-xs text-muted-foreground">{i.hint}</span>}
                      {idx === active && <CornerDownLeft className="relative h-3.5 w-3.5 shrink-0" />}
                    </button>
                  </li>
                );
              })}
            </ul>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
