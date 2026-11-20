"use client";

import { AnimatePresence, motion } from "framer-motion";
import { CheckCircle2, Cpu, KeyRound, Loader2, PlugZap, Power, Sparkles, X, XCircle } from "lucide-react";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { type LLMSettings, useLLMSettings, useSaveLLMSettings, useTestLLM } from "@/lib/research-api";
import { cn } from "@/lib/utils";

type Mode = LLMSettings["mode"];

const MODES: { id: Mode; title: string; body: string; icon: typeof Power }[] = [
  {
    id: "off",
    title: "Off: cited extracts",
    body: "Findings are quoted straight from each source with its link. No AI writing, no key needed.",
    icon: Power,
  },
  {
    id: "ollama",
    title: "Local model (Ollama)",
    body: "Runs on this machine. Free and private. Needs Ollama with a 7B+ model.",
    icon: Cpu,
  },
  {
    id: "openai_compatible",
    title: "API key",
    body: "OpenAI, Groq, Gemini, OpenRouter or any OpenAI-compatible endpoint (including Emergent).",
    icon: KeyRound,
  },
];

/** Header button showing whether AI summaries are on. */
export function LLMButton({ onClick }: { onClick: () => void }) {
  const s = useLLMSettings();
  const on = s.data && s.data.mode !== "off" && !s.data.active.startsWith("extractive");
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "pressable flex h-9 items-center gap-2 rounded-lg border px-3 text-sm font-medium",
        on ? "border-primary/40 bg-primary/10 text-foreground" : "bg-card/70 text-muted-foreground",
      )}
      title={s.data?.active}
    >
      <span className="relative flex h-2 w-2">
        {on && <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-primary opacity-60" />}
        <span className={cn("relative inline-flex h-2 w-2 rounded-full", on ? "bg-primary" : "bg-muted-foreground/50")} />
      </span>
      <Sparkles className="h-4 w-4" />
      <span className="hidden md:inline">{on ? "AI summaries on" : "Connect LLM"}</span>
    </button>
  );
}

/** Right-side panel to connect an LLM for AI summaries (or keep extractive mode). */
export function LLMPanel({ open, onClose }: { open: boolean; onClose: () => void }) {
  const s = useLLMSettings();
  const save = useSaveLLMSettings();
  const test = useTestLLM();
  const [mode, setMode] = useState<Mode>("off");
  const [provider, setProvider] = useState("groq");
  const [baseUrl, setBaseUrl] = useState("");
  const [model, setModel] = useState("");
  const [apiKey, setApiKey] = useState("");

  useEffect(() => {
    if (!open || !s.data) return;
    setMode(s.data.mode);
    setProvider(s.data.provider || "groq");
    setBaseUrl(s.data.base_url);
    setModel(s.data.model);
    setApiKey("");
    test.reset();
  }, [open, s.data]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    if (open) window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  const presets = s.data?.presets ?? {};
  const pickPreset = (p: string) => {
    setProvider(p);
    if (presets[p]) {
      setBaseUrl(presets[p].base_url);
      setModel(presets[p].model);
    } else if (p === "custom") {
      setBaseUrl("");
      setModel("");
    }
  };

  const body = () => ({
    mode,
    provider: mode === "openai_compatible" ? provider : mode === "ollama" ? "ollama" : "",
    base_url: mode === "ollama" ? baseUrl || "http://localhost:11434" : mode === "openai_compatible" ? baseUrl : "",
    model: mode === "off" ? "" : model,
    api_key: apiKey || undefined,
  });

  return (
    <AnimatePresence>
      {open && (
        <>
          <motion.div
            className="fixed inset-0 z-40 bg-foreground/25 backdrop-blur-[2px]"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
          />
          <motion.aside
            role="dialog"
            aria-label="AI summaries"
            className="fixed inset-y-0 right-0 z-50 flex w-full max-w-md flex-col border-l bg-card shadow-2xl"
            initial={{ x: "100%" }}
            animate={{ x: 0 }}
            exit={{ x: "100%" }}
            transition={{ type: "spring", stiffness: 380, damping: 40 }}
          >
            <div className="flex items-start justify-between gap-4 border-b p-5">
              <div>
                <h2 className="text-lg font-semibold">AI summaries</h2>
                <p className="mt-1 text-sm text-muted-foreground">
                  Optional. Research always works without it: every finding stays quoted and linked to its source.
                </p>
              </div>
              <Button variant="ghost" size="icon" onClick={onClose} aria-label="Close">
                <X className="h-4 w-4" />
              </Button>
            </div>

            <div className="flex-1 space-y-5 overflow-y-auto p-5">
              <div className="space-y-2">
                {MODES.map((m) => {
                  const Icon = m.icon;
                  const active = mode === m.id;
                  return (
                    <button
                      key={m.id}
                      type="button"
                      onClick={() => {
                        setMode(m.id);
                        test.reset();
                        if (m.id === "openai_compatible" && !baseUrl) pickPreset(provider || "groq");
                        if (m.id === "ollama" && !baseUrl.includes("11434")) {
                          setBaseUrl("http://localhost:11434");
                          setModel("");
                        }
                      }}
                      className={cn(
                        "pressable relative flex w-full gap-3 rounded-xl border p-3 text-left",
                        active ? "border-primary/50" : "",
                      )}
                    >
                      {active && (
                        <motion.span
                          layoutId="llm-mode"
                          className="absolute inset-0 rounded-xl bg-primary/10"
                          transition={{ type: "spring", stiffness: 450, damping: 38 }}
                        />
                      )}
                      <Icon className={cn("relative mt-0.5 h-5 w-5 shrink-0", active ? "text-primary" : "text-muted-foreground")} />
                      <span className="relative">
                        <span className="block text-sm font-medium">{m.title}</span>
                        <span className="mt-0.5 block text-xs text-muted-foreground">{m.body}</span>
                      </span>
                    </button>
                  );
                })}
              </div>

              <AnimatePresence mode="wait" initial={false}>
                {mode === "openai_compatible" && (
                  <motion.div
                    key="api"
                    initial={{ opacity: 0, y: 6 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -6 }}
                    transition={{ duration: 0.18 }}
                    className="space-y-3"
                  >
                    <div className="flex flex-wrap gap-1.5">
                      {[...Object.keys(presets), "custom"].map((p) => (
                        <button
                          key={p}
                          type="button"
                          onClick={() => pickPreset(p)}
                          className={cn(
                            "rounded-full border px-3 py-1 text-xs capitalize transition-colors",
                            provider === p ? "border-primary bg-primary/15 text-foreground" : "text-muted-foreground hover:bg-secondary",
                          )}
                        >
                          {p}
                        </button>
                      ))}
                    </div>
                    <div className="space-y-1.5">
                      <Label htmlFor="llm-key">API key</Label>
                      <Input
                        id="llm-key"
                        type="password"
                        autoComplete="off"
                        value={apiKey}
                        onChange={(e) => setApiKey(e.target.value)}
                        placeholder={s.data?.has_key ? `Saved (${s.data.key_hint}). Leave blank to keep it.` : "Paste your key"}
                      />
                      <p className="text-[11px] text-muted-foreground">Stored on the server only. It is never sent back to the browser.</p>
                    </div>
                    <div className="space-y-1.5">
                      <Label htmlFor="llm-url">API base URL</Label>
                      <Input id="llm-url" value={baseUrl} onChange={(e) => setBaseUrl(e.target.value)} placeholder="https://…/v1" />
                    </div>
                    <div className="space-y-1.5">
                      <Label htmlFor="llm-model">Model</Label>
                      <Input id="llm-model" value={model} onChange={(e) => setModel(e.target.value)} placeholder="e.g. gpt-4o-mini" />
                    </div>
                  </motion.div>
                )}
                {mode === "ollama" && (
                  <motion.div
                    key="ollama"
                    initial={{ opacity: 0, y: 6 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -6 }}
                    transition={{ duration: 0.18 }}
                    className="space-y-3"
                  >
                    <div className="space-y-1.5">
                      <Label htmlFor="ol-url">Ollama URL</Label>
                      <Input id="ol-url" value={baseUrl} onChange={(e) => setBaseUrl(e.target.value)} placeholder="http://localhost:11434" />
                    </div>
                    <div className="space-y-1.5">
                      <Label htmlFor="ol-model">Model (blank = pick the best installed 7B+ model)</Label>
                      <Input id="ol-model" value={model} onChange={(e) => setModel(e.target.value)} placeholder="qwen2.5:7b-instruct" />
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>

              <div className="rounded-xl border border-dashed p-3 text-xs text-muted-foreground">
                With AI on, sections are written by the model, but a finding is marked{" "}
                <span className="font-medium text-foreground">source-supported</span> only when its quote is found word for
                word in the cited page. AI-written prose is always labelled.
              </div>

              <AnimatePresence>
                {test.data && (
                  <motion.div
                    initial={{ opacity: 0, scale: 0.98 }}
                    animate={{ opacity: 1, scale: 1 }}
                    exit={{ opacity: 0 }}
                    className={cn(
                      "flex items-start gap-2 rounded-xl border p-3 text-sm",
                      test.data.ok
                        ? "border-primary/40 bg-primary/10"
                        : "border-destructive/40 bg-destructive/10",
                    )}
                  >
                    {test.data.ok ? (
                      <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-primary" />
                    ) : (
                      <XCircle className="mt-0.5 h-4 w-4 shrink-0 text-destructive" />
                    )}
                    {test.data.message}
                  </motion.div>
                )}
              </AnimatePresence>
            </div>

            <div className="flex items-center justify-between gap-2 border-t p-4">
              <span className="text-xs text-muted-foreground">Now: {s.data?.active ?? "…"}</span>
              <div className="flex gap-2">
                <Button variant="outline" size="sm" disabled={test.isPending} onClick={() => test.mutate(body())}>
                  {test.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <PlugZap className="h-4 w-4" />}
                  Test
                </Button>
                <Button size="sm" disabled={save.isPending} onClick={() => save.mutate(body(), { onSuccess: onClose })}>
                  {save.isPending && <Loader2 className="h-4 w-4 animate-spin" />}
                  {mode === "off" ? "Use cited extracts" : "Save and connect"}
                </Button>
              </div>
            </div>
          </motion.aside>
        </>
      )}
    </AnimatePresence>
  );
}
