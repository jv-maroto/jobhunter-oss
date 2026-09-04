"use client";

/**
 * CapabilityBanner — yellow strip that shows /health warnings.
 *
 * The most common one: `typst` binary not installed, which silently breaks
 * "Prepare application" (used to fail later with a misleading "CV file
 * missing on disk" download error). Now the user sees the real cause on
 * every page until they fix it.
 *
 * Dismissible per-session via sessionStorage so it doesn't nag once the
 * user has read it (but comes back on the next reload if still broken).
 */

import * as React from "react";
import { AlertTriangle, X } from "lucide-react";
import { useBackendHealth } from "@/hooks/useBackendHealth";

const DISMISS_KEY = "capability-banner-dismissed";

export function CapabilityBanner() {
  const { data } = useBackendHealth();
  const [dismissed, setDismissed] = React.useState(false);

  React.useEffect(() => {
    try {
      setDismissed(sessionStorage.getItem(DISMISS_KEY) === "1");
    } catch {
      /* SSR / no storage */
    }
  }, []);

  const warnings = data?.warnings ?? [];
  if (!warnings.length || dismissed) return null;

  return (
    <div className="border-b border-amber-500/30 bg-amber-500/10 px-5 py-2.5 lg:px-6">
      <div className="mx-auto flex items-start gap-3 max-w-6xl">
        <AlertTriangle className="h-4 w-4 shrink-0 mt-0.5 text-amber-300" />
        <div className="flex-1 space-y-1 text-xs text-amber-100">
          {warnings.map((w, i) => (
            <div key={i} className="whitespace-pre-line">
              {w}
            </div>
          ))}
        </div>
        <button
          type="button"
          onClick={() => {
            try {
              sessionStorage.setItem(DISMISS_KEY, "1");
            } catch {
              /* noop */
            }
            setDismissed(true);
          }}
          title="Dismiss until reload"
          className="shrink-0 text-amber-300 hover:text-amber-100"
        >
          <X className="h-4 w-4" />
        </button>
      </div>
    </div>
  );
}
