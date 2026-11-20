"use client";

import {
  Building2,
  FlaskConical,
  Newspaper,
  GitCompareArrows,
  LayoutDashboard,
  Menu,
  Search,
  FileText,
  Settings,
  Signal,
} from "lucide-react";
import { motion } from "framer-motion";
import Image from "next/image";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState, type ReactNode } from "react";

import { CommandPalette } from "@/components/command-palette";
import { ThemeToggle } from "@/components/theme-toggle";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogTrigger } from "@/components/ui/dialog";
import { cn } from "@/lib/utils";

const NAV = [
  { href: "/dashboard", label: "Overview", icon: LayoutDashboard },
  { href: "/research", label: "Research", icon: FlaskConical },
  { href: "/feed", label: "Feed", icon: Newspaper },
  { href: "/competitors", label: "Companies", icon: Building2 },
  { href: "/signals", label: "Signals", icon: Signal },
  { href: "/changes", label: "Changes", icon: GitCompareArrows },
  { href: "/reports", label: "Reports", icon: FileText },
  { href: "/settings", label: "Settings", icon: Settings },
];

// The bottom bar fits five comfortably; Settings stays in the sidebar/menu.
const MOBILE_NAV = NAV.filter((n) =>
  ["/dashboard", "/research", "/feed", "/competitors", "/reports"].includes(n.href),
);

function isActive(pathname: string, href: string): boolean {
  return href === "/dashboard" ? pathname === "/dashboard" : pathname.startsWith(href);
}

function NavLinks({ pathname, onNavigate }: { pathname: string; onNavigate?: () => void }) {
  return (
    <nav className="flex flex-col gap-1">
      {NAV.map(({ href, label, icon: Icon }) => {
        const active = isActive(pathname, href);
        return (
          <Link
            key={href}
            href={href}
            onClick={onNavigate}
            className={cn(
              "relative flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors active:scale-[0.98]",
              active ? "text-foreground" : "text-muted-foreground hover:bg-secondary/60 hover:text-foreground",
            )}
            aria-current={active ? "page" : undefined}
          >
            {active && (
              <motion.span
                layoutId="nav-active"
                className="absolute inset-0 rounded-lg border border-primary/25 bg-primary/10"
                transition={{ type: "spring", stiffness: 420, damping: 36 }}
              >
                <span className="absolute inset-y-2 left-0 w-1 rounded-full bg-primary" />
              </motion.span>
            )}
            <Icon className="relative h-4 w-4" />
            <span className="relative">{label}</span>
          </Link>
        );
      })}
    </nav>
  );
}

function Brand() {
  return (
    <Link href="/dashboard" className="flex items-center gap-2 px-1 py-1">
      <Image
        src="/compete-logo.svg"
        alt="compete logo"
        width={32}
        height={32}
        priority
        className="h-8 w-8 rounded-lg hue-rotate-[100deg]"
      />
      <span className="text-base font-semibold leading-tight tracking-tight">Market Intel<span className="block text-[10px] font-normal text-muted-foreground">India-first tracker</span></span>
    </Link>
  );
}

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);

  return (
    <div className="min-h-screen">
      {/* Desktop sidebar */}
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-64 flex-col border-r bg-card/40 px-3 py-4 md:flex">
        <Brand />
        <div className="mt-6 flex-1">
          <NavLinks pathname={pathname} />
        </div>
        <div className="px-1">
          <p className="px-2 text-xs text-muted-foreground">
            Market Intelligence Tracker
            <br />
            <span className="text-muted-foreground/60">Built on compete (MIT)</span>
          </p>
        </div>
      </aside>

      <div className="md:pl-64">
        {/* Top bar */}
        <header className="sticky top-0 z-20 flex h-14 items-center gap-3 border-b bg-background/80 px-4 backdrop-blur supports-[backdrop-filter]:bg-background/60">
          {/* Mobile menu */}
          <Dialog open={open} onOpenChange={setOpen}>
            <DialogTrigger asChild>
              <Button variant="outline" size="icon" className="md:hidden" aria-label="Open menu">
                <Menu className="h-4 w-4" />
              </Button>
            </DialogTrigger>
            <DialogContent className="left-0 top-0 h-full max-w-[16rem] translate-x-0 translate-y-0 rounded-none border-r data-[state=closed]:slide-out-to-left data-[state=open]:slide-in-from-left">
              <Brand />
              <div className="mt-4">
                <NavLinks pathname={pathname} onNavigate={() => setOpen(false)} />
              </div>
            </DialogContent>
          </Dialog>

          <Link href="/dashboard" className="flex items-center gap-2 md:hidden">
            <Image
              src="/compete-logo.svg"
              alt="compete logo"
              width={24}
              height={24}
              className="h-6 w-6 rounded-md hue-rotate-[100deg]"
            />
            <span className="font-semibold">Market Intel</span>
          </Link>

          <button
            type="button"
            onClick={() => window.dispatchEvent(new Event("open-command-palette"))}
            className="pressable ml-auto hidden h-9 w-72 items-center gap-2 rounded-lg border bg-card/70 px-3 text-sm text-muted-foreground sm:flex"
          >
            <Search className="h-4 w-4" />
            <span className="flex-1 text-left">Jump to…</span>
            <kbd className="rounded border bg-muted px-1.5 text-[11px]">Ctrl K</kbd>
          </button>
          <div className="ml-auto flex items-center gap-2 sm:ml-0">
            <ThemeToggle />
          </div>
        </header>

        <main className="mx-auto w-full max-w-7xl px-4 pb-24 pt-6 md:px-8 md:pb-10">
          {children}
        </main>
      </div>

      <CommandPalette />

      {/* Mobile bottom nav */}
      <nav className="fixed inset-x-0 bottom-0 z-30 grid grid-cols-5 border-t bg-background/95 backdrop-blur md:hidden">
        {MOBILE_NAV.map(({ href, label, icon: Icon }) => {
          const active = isActive(pathname, href);
          return (
            <Link
              key={href}
              href={href}
              className={cn(
                "flex flex-col items-center gap-1 py-2 text-[11px]",
                active ? "text-primary" : "text-muted-foreground",
              )}
              aria-current={active ? "page" : undefined}
            >
              <Icon className="h-5 w-5" />
              {label}
            </Link>
          );
        })}
      </nav>
    </div>
  );
}
