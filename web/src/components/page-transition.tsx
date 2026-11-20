"use client";

import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

/**
 * Subtle fade/translate entrance on navigation. Pure CSS (see `.animate-enter`
 * in globals.css) so content is never left invisible if JS animation frames are
 * paused, e.g. in a background tab. Keyed on pathname to re-run per route.
 */
export function PageTransition({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  return (
    <div key={pathname} className="animate-enter">
      {children}
    </div>
  );
}
