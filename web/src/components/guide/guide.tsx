"use client";

import * as DialogPrimitive from "@radix-ui/react-dialog";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { ArrowUp, Check, Copy, RotateCcw, Square, WifiOff, X } from "lucide-react";
import { usePathname, useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { Streamdown } from "streamdown";
import "streamdown/styles.css";

import { GuideBot } from "@/components/guide/guide-bot";
import { useActivity } from "@/lib/activity";
import { cn } from "@/lib/utils";

const BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "/api";
const META = "\n\n<<META>>";
const HISTORY_KEY = "mi-guide-chat-v1";
const OPENED_KEY = "mi-guide-opened";

interface Meta {
  actions?: { label: string; route: string }[];
  suggestions?: string[];
  sources?: string[];
}
interface Msg {
  id: string;
  role: "user" | "assistant";
  content: string;
  meta?: Meta;
  error?: boolean;
}

const PAGE: [string, string][] = [
  ["/research/view", "a research report"],
  ["/research", "Research"],
  ["/feed", "Feed"],
  ["/competitors/", "a company profile"],
  ["/competitors", "Companies"],
  ["/dashboard", "Overview"],
  ["/signals", "Signals"],
  ["/changes", "Changes"],
  ["/reports", "Reports"],
  ["/settings", "Settings"],
];
const pageName = (p: string) => PAGE.find(([k]) => p.startsWith(k))?.[1] ?? "the app";

function readJSON<T>(store: Storage | undefined, key: string, fallback: T): T {
  try {
    const raw = store?.getItem(key);
    return raw ? (JSON.parse(raw) as T) : fallback;
  } catch {
    return fallback;
  }
}

/** Floating launcher + chat panel. Mounted once in the app shell. */
export function Guide() {
  const [open, setOpen] = useState(false);
  const [seen, setSeen] = useState(true);
  const [messages, setMessages] = useState<Msg[]>([]);
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [thinking, setThinking] = useState(false);
  const [offline, setOffline] = useState(false);
  const [starters, setStarters] = useState<string[]>([]);
  const [copied, setCopied] = useState<string | null>(null);
  const abort = useRef<AbortController | null>(null);
  const listRef = useRef<HTMLDivElement>(null);
  const stick = useRef(true);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const pathname = usePathname() ?? "/";
  const router = useRouter();
  const reduce = useReducedMotion();
  const { entries, log } = useActivity();

  useEffect(() => {
    setMessages(readJSON<Msg[]>(typeof window !== "undefined" ? sessionStorage : undefined, HISTORY_KEY, []));
    setSeen(readJSON<boolean>(typeof window !== "undefined" ? localStorage : undefined, OPENED_KEY, false));
  }, []);

  useEffect(() => {
    if (streaming) return;
    try {
      sessionStorage.setItem(HISTORY_KEY, JSON.stringify(messages.slice(-30)));
    } catch {
      /* ignore */
    }
  }, [messages, streaming]);

  const openGuide = useCallback((prefill?: string) => {
    setOpen(true);
    setSeen(true);
    try {
      localStorage.setItem(OPENED_KEY, "true");
    } catch {
      /* ignore */
    }
    if (prefill) setInput(prefill);
    setTimeout(() => inputRef.current?.focus(), 120);
  }, []);

  // Ctrl+/ toggles; the palette dispatches "open-guide".
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === "/") {
        e.preventDefault();
        setOpen((o) => {
          if (!o) openGuide();
          return !o;
        });
      }
    };
    const onOpen = (e: Event) => openGuide((e as CustomEvent<string | undefined>).detail);
    window.addEventListener("keydown", onKey);
    window.addEventListener("open-guide", onOpen);
    return () => {
      window.removeEventListener("keydown", onKey);
      window.removeEventListener("open-guide", onOpen);
    };
  }, [openGuide]);

  useEffect(() => {
    if (!open) return;
    fetch(`${BASE}/assistant/starters?pathname=${encodeURIComponent(pathname)}`)
      .then((r) => (r.ok ? r.json() : Promise.reject()))
      .then((d) => {
        setStarters(d.starters ?? []);
        setOffline(false);
      })
      .catch(() => setOffline(true));
  }, [open, pathname]);

  // Auto-scroll unless the user scrolled up.
  useEffect(() => {
    const el = listRef.current;
    if (el && stick.current) el.scrollTo({ top: el.scrollHeight, behavior: reduce ? "auto" : "smooth" });
  }, [messages, thinking, reduce]);

  const send = async (text: string) => {
    const message = text.trim();
    if (!message || streaming) return;
    setInput("");
    stick.current = true;
    const userMsg: Msg = { id: `u${Date.now()}`, role: "user", content: message };
    const botId = `a${Date.now()}`;
    const history = messages.slice(-6).map((m) => ({ role: m.role, content: m.content.slice(0, 1500) }));
    setMessages((m) => [...m, userMsg]);
    setStreaming(true);
    setThinking(true);
    const ctrl = new AbortController();
    abort.current = ctrl;
    const activity = entries.slice(-10).map((e) => ({
      label: e.label, status: e.status, durationMs: e.durationMs, error: e.error, route: e.route, kind: e.kind,
    }));
    let acc = "";
    let started = false;
    try {
      const res = await fetch(`${BASE}/assistant/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message, pathname, history, activity }),
        signal: ctrl.signal,
      });
      if (!res.ok || !res.body) throw new Error(`Guide request failed (${res.status})`);
      setOffline(false);
      const reader = res.body.getReader();
      const dec = new TextDecoder();
      for (;;) {
        const { value, done } = await reader.read();
        if (done) break;
        acc += dec.decode(value, { stream: true });
        const visible = acc.includes(META) ? acc.slice(0, acc.indexOf(META)) : acc.replace(/\n\n<<M?E?T?A?>?>?$/, "");
        if (!started) {
          started = true;
          setThinking(false);
          setMessages((m) => [...m, { id: botId, role: "assistant", content: visible }]);
        } else {
          setMessages((m) => m.map((x) => (x.id === botId ? { ...x, content: visible } : x)));
        }
      }
      let meta: Meta | undefined;
      if (acc.includes(META)) {
        try {
          meta = JSON.parse(acc.slice(acc.indexOf(META) + META.length)) as Meta;
        } catch {
          meta = undefined;
        }
      }
      const finalText = acc.includes(META) ? acc.slice(0, acc.indexOf(META)) : acc;
      setMessages((m) =>
        started
          ? m.map((x) => (x.id === botId ? { ...x, content: finalText, meta } : x))
          : [...m, { id: botId, role: "assistant", content: finalText, meta }],
      );
    } catch (err) {
      const aborted = err instanceof DOMException && err.name === "AbortError";
      if (!aborted) setOffline(true);
      setMessages((m) => {
        const has = m.some((x) => x.id === botId);
        const note = aborted ? "\n\n_Stopped._" : "";
        if (has) return m.map((x) => (x.id === botId ? { ...x, content: x.content + note } : x));
        return aborted
          ? [...m, { id: botId, role: "assistant", content: "_Stopped._" }]
          : [...m, { id: botId, role: "assistant", content: "The guide needs the API running. Start the backend and try again.", error: true }];
      });
    } finally {
      setThinking(false);
      setStreaming(false);
      abort.current = null;
    }
  };

  const copy = async (m: Msg) => {
    try {
      await navigator.clipboard.writeText(m.content);
      setCopied(m.id);
      log({ kind: "action", label: "Copied a guide answer" });
      setTimeout(() => setCopied(null), 1400);
    } catch {
      /* clipboard blocked */
    }
  };

  const last = messages[messages.length - 1];
  const chips = !messages.length ? starters : last?.role === "assistant" && !streaming ? last.meta?.suggestions ?? [] : [];

  return (
    <>
      {/* Launcher */}
      <AnimatePresence>
        {!open && (
          <motion.button
            type="button"
            aria-label="Open the guide (Ctrl+/)"
            onClick={() => openGuide()}
            className="fixed bottom-20 right-3 z-40 flex items-center gap-1 rounded-full border bg-card/90 p-1 shadow-lg backdrop-blur sm:pr-3 md:bottom-6 md:right-6"
            initial={{ scale: 0.6, opacity: 0, y: 20 }}
            animate={{ scale: 1, opacity: 1, y: 0 }}
            exit={{ scale: 0.6, opacity: 0, y: 20 }}
            whileHover={{ scale: 1.04 }}
            whileTap={{ scale: 0.95 }}
            transition={{ type: "spring", stiffness: 420, damping: 26 }}
          >
            {!seen && <span className="absolute inset-0 animate-ping rounded-full bg-primary/25" />}
            <GuideBot size={44} />
            <span className="relative hidden text-sm font-medium sm:inline">Ask the guide</span>
          </motion.button>
        )}
      </AnimatePresence>

      <DialogPrimitive.Root open={open} onOpenChange={setOpen} modal>
        <AnimatePresence>
          {open && (
            <DialogPrimitive.Portal forceMount>
              <DialogPrimitive.Content
                forceMount
                aria-describedby={undefined}
                onOpenAutoFocus={(e) => {
                  e.preventDefault();
                  inputRef.current?.focus();
                }}
                className="fixed inset-x-0 bottom-0 top-0 z-50 outline-none sm:inset-auto sm:bottom-6 sm:right-6"
              >
                <motion.div
                  className="flex h-full w-full flex-col overflow-hidden border bg-card shadow-2xl sm:h-[560px] sm:w-[380px] sm:rounded-2xl"
                  initial={{ opacity: 0, y: 24, scale: 0.96 }}
                  animate={{ opacity: 1, y: 0, scale: 1 }}
                  exit={{ opacity: 0, y: 24, scale: 0.96 }}
                  transition={{ type: "spring", stiffness: 380, damping: 32 }}
                  style={{ transformOrigin: "bottom right" }}
                >
                  {/* Header */}
                  <div className="flex items-center gap-2 border-b px-3 py-2">
                    <GuideBot size={40} thinking={thinking || streaming} />
                    <div className="min-w-0 flex-1">
                      <DialogPrimitive.Title className="font-display text-base font-semibold leading-tight">
                        Guide
                      </DialogPrimitive.Title>
                      <p className="truncate text-xs text-muted-foreground">You&apos;re on {pageName(pathname)}</p>
                    </div>
                    <button
                      type="button"
                      onClick={() => {
                        abort.current?.abort();
                        setMessages([]);
                      }}
                      className="rounded-md p-1.5 text-muted-foreground hover:bg-secondary hover:text-foreground"
                      aria-label="New chat"
                      title="New chat"
                    >
                      <RotateCcw className="h-4 w-4" />
                    </button>
                    <DialogPrimitive.Close
                      className="rounded-md p-1.5 text-muted-foreground hover:bg-secondary hover:text-foreground"
                      aria-label="Close guide"
                    >
                      <X className="h-4 w-4" />
                    </DialogPrimitive.Close>
                  </div>

                  {/* Messages */}
                  <div
                    ref={listRef}
                    onScroll={(e) => {
                      const el = e.currentTarget;
                      stick.current = el.scrollHeight - el.scrollTop - el.clientHeight < 40;
                    }}
                    className="flex-1 space-y-3 overflow-y-auto px-3 py-3"
                    aria-live="polite"
                  >
                    {!messages.length && (
                      <div className="px-1 pt-2 text-sm text-muted-foreground">
                        <p className="font-medium text-foreground">Hi, I&apos;m Volt.</p>
                        <p className="mt-1">
                          I know how this app works: where things are, what the labels mean, and what your research is
                          doing right now. I won&apos;t make things up.
                        </p>
                      </div>
                    )}
                    {offline && (
                      <div className="flex items-start gap-2 rounded-xl border border-amber-500/40 bg-amber-500/10 p-2.5 text-xs">
                        <WifiOff className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                        <span className="flex-1">The guide needs the API running.</span>
                        <button
                          type="button"
                          className="font-medium text-primary hover:underline"
                          onClick={() => {
                            setOffline(false);
                            fetch(`${BASE}/assistant/starters?pathname=${encodeURIComponent(pathname)}`)
                              .then((r) => (r.ok ? r.json() : Promise.reject()))
                              .then((d) => setStarters(d.starters ?? []))
                              .catch(() => setOffline(true));
                          }}
                        >
                          Retry
                        </button>
                      </div>
                    )}
                    {messages.map((m, i) => {
                      const isLast = i === messages.length - 1;
                      const live = isLast && streaming && m.role === "assistant";
                      return (
                        <motion.div
                          key={m.id}
                          initial={reduce ? false : { opacity: 0, y: 6 }}
                          animate={{ opacity: 1, y: 0 }}
                          transition={{ duration: 0.18 }}
                          className={cn("flex", m.role === "user" ? "justify-end" : "justify-start")}
                        >
                          {m.role === "user" ? (
                            <div className="max-w-[85%] rounded-2xl rounded-br-md bg-primary px-3 py-2 text-sm text-primary-foreground">
                              {m.content}
                            </div>
                          ) : (
                            <div className="group max-w-[92%]">
                              <div
                                className={cn(
                                  "guide-md rounded-2xl rounded-bl-md border bg-background/60 px-3 py-2 text-sm",
                                  m.error && "border-destructive/40",
                                )}
                              >
                                <Streamdown
                                  mode={live ? "streaming" : "static"}
                                  isAnimating={live}
                                  animated={reduce ? false : { animation: "blurIn" }}
                                  caret={live ? "block" : undefined}
                                  controls={false}
                                >
                                  {m.content}
                                </Streamdown>
                              </div>
                              {!live && (m.meta?.actions?.length || !m.error) ? (
                                <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
                                  {m.meta?.actions?.map((a) => (
                                    <motion.button
                                      key={a.route + a.label}
                                      type="button"
                                      whileTap={{ scale: 0.96 }}
                                      onClick={() => {
                                        log({ kind: "action", label: `Guide: ${a.label}`, route: a.route });
                                        router.push(a.route);
                                        if (window.innerWidth < 640) setOpen(false);
                                      }}
                                      className="rounded-full border border-primary/40 bg-primary/10 px-3 py-1 text-xs font-medium hover:bg-primary/20"
                                    >
                                      {a.label}
                                    </motion.button>
                                  ))}
                                  {!m.error && (
                                    <button
                                      type="button"
                                      onClick={() => copy(m)}
                                      className="rounded-md p-1 text-muted-foreground opacity-70 hover:bg-secondary hover:opacity-100"
                                      aria-label="Copy answer"
                                    >
                                      {copied === m.id ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
                                    </button>
                                  )}
                                </div>
                              ) : null}
                            </div>
                          )}
                        </motion.div>
                      );
                    })}
                    {thinking && (
                      <div className="flex gap-1 px-2 py-1" aria-label="Guide is typing">
                        {[0, 1, 2].map((d) => (
                          <motion.span
                            key={d}
                            className="h-1.5 w-1.5 rounded-full bg-muted-foreground"
                            animate={reduce ? undefined : { y: [0, -4, 0], opacity: [0.4, 1, 0.4] }}
                            transition={{ duration: 0.9, repeat: Infinity, delay: d * 0.15 }}
                          />
                        ))}
                      </div>
                    )}
                  </div>

                  {/* Chips */}
                  <AnimatePresence>
                    {chips.length > 0 && (
                      <motion.div
                        initial={{ opacity: 0, y: 4 }}
                        animate={{ opacity: 1, y: 0 }}
                        exit={{ opacity: 0 }}
                        className="flex flex-wrap gap-1.5 px-3 pb-2"
                      >
                        {chips.map((c) => (
                          <button
                            key={c}
                            type="button"
                            onClick={() => send(c)}
                            className="rounded-full border px-2.5 py-1 text-xs text-muted-foreground transition-colors hover:border-primary/50 hover:text-foreground"
                          >
                            {c}
                          </button>
                        ))}
                      </motion.div>
                    )}
                  </AnimatePresence>

                  {/* Composer */}
                  <form
                    className="flex items-end gap-2 border-t p-2.5"
                    onSubmit={(e) => {
                      e.preventDefault();
                      send(input);
                    }}
                  >
                    <textarea
                      ref={inputRef}
                      rows={1}
                      value={input}
                      onChange={(e) => setInput(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === "Enter" && !e.shiftKey) {
                          e.preventDefault();
                          send(input);
                        }
                      }}
                      maxLength={1000}
                      placeholder="Ask about this app…"
                      className="max-h-28 min-h-[38px] flex-1 resize-none rounded-xl border bg-background px-3 py-2 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring"
                    />
                    {streaming ? (
                      <motion.button
                        type="button"
                        whileTap={{ scale: 0.92 }}
                        onClick={() => abort.current?.abort()}
                        className="flex h-[38px] w-[38px] items-center justify-center rounded-xl border bg-secondary"
                        aria-label="Stop"
                      >
                        <Square className="h-3.5 w-3.5 fill-current" />
                      </motion.button>
                    ) : (
                      <motion.button
                        type="submit"
                        whileTap={{ scale: 0.92 }}
                        disabled={!input.trim()}
                        className="flex h-[38px] w-[38px] items-center justify-center rounded-xl bg-primary text-primary-foreground disabled:opacity-40"
                        aria-label="Send"
                      >
                        <ArrowUp className="h-4 w-4" />
                      </motion.button>
                    )}
                  </form>
                </motion.div>
              </DialogPrimitive.Content>
            </DialogPrimitive.Portal>
          )}
        </AnimatePresence>
      </DialogPrimitive.Root>
    </>
  );
}
