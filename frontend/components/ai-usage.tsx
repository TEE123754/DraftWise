"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api/client";

export type AiUsageData = { scope: "day" | "demo_session"; used: number; budget: number; remaining: number };

/** "AI calls used: 2 / 30 today": what has been spent and the allowance it counts against. */
export function AiUsageText({ usage }: { usage: AiUsageData }) {
  const window = usage.scope === "demo_session" ? "in this demo session" : "today";
  return (
    <span data-testid="ai-usage">
      AI calls used: <strong>{usage.used}</strong> / {usage.budget} {window}
      {usage.budget > 0 && usage.remaining === 0 ? " (used up: rules are used instead)" : ""}
    </span>
  );
}

export function AiUsage({ className }: { className?: string }) {
  const [usage, setUsage] = useState<AiUsageData | null>(null);
  useEffect(() => {
    const controller = new AbortController();
    api<AiUsageData>("/quality/ai-usage", { signal: controller.signal })
      .then((value) => setUsage(typeof value?.budget === "number" ? value : null))
      .catch(() => setUsage(null));
    return () => controller.abort();
  }, []);
  return usage ? (
    <p className={className ?? "text-xs text-slate-700"}>
      <AiUsageText usage={usage} />
    </p>
  ) : null;
}
