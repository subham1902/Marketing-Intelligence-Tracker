import type { Metadata } from "next";
import type { ReactNode } from "react";
import { Bricolage_Grotesque, IBM_Plex_Sans, Instrument_Serif } from "next/font/google";

import { Providers } from "@/components/providers";
import "./globals.css";

const sans = IBM_Plex_Sans({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-sans",
  display: "swap",
});

const display = Bricolage_Grotesque({
  subsets: ["latin"],
  variable: "--font-display",
  display: "swap",
});

const serif = Instrument_Serif({
  subsets: ["latin"],
  weight: "400",
  style: ["normal", "italic"],
  variable: "--font-serif",
  display: "swap",
});

// Absolute base for canonical + OG/Twitter URLs. Override per-deploy with
// NEXT_PUBLIC_SITE_URL (set in Vercel to the real domain); the fallback is the
// intended production URL so shares still resolve if the env var is missing.
const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL ?? "https://compete.yerradouani.me";

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  title: {
    default: "Market Intelligence Tracker — India-first market & competitor research",
    template: "%s · compete",
  },
  description:
    "India-first market intelligence: company tracking, on-demand research from free public sources, and policy and tender discovery, with every finding linked to its source.",
  icons: {
    icon: [{ url: "/mi-logo.svg", type: "image/svg+xml" }],
    shortcut: "/mi-logo.svg",
    apple: "/mi-logo.svg",
  },
  openGraph: {
    title: "Market Intelligence Tracker — India-first market & competitor research",
    description:
      "Track every move your competitors make. Pricing, hiring, launches, messaging - ranked and explained.",
    type: "website",
  },
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning className={`${sans.variable} ${display.variable} ${serif.variable}`}>
      <body className="font-sans">
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
