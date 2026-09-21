"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api/client";

type Progress = {
  eligible: number;
  read: number;
  compared: number;
  failed: number;
  active: boolean;
};

const POLL_MS = 4000;

/**
 * How far the background reading and comparison of a mailbox has got. Right after the demo opens
 * the worker is still going through the comparison emails, and a bare "Processing" label gives no
 * sense of whether anything is happening. It polls only while work is in flight and disappears
 * once nothing is left; a failure to load it never affects the page around it.
 */
export function ReadingProgress() {
  const [progress, setProgress] = useState<Progress | null>(null);

  useEffect(() => {
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const controller = new AbortController();

    async function tick() {
      let next: Progress | null = null;
      try {
        next = await api<Progress>("/workspace/processing", { signal: controller.signal });
      } catch {
        next = null;
      }
      if (cancelled) return;
      setProgress(next);
      if (next?.active) timer = setTimeout(() => void tick(), POLL_MS);
    }
    void tick();
    return () => {
      cancelled = true;
      controller.abort();
      if (timer) clearTimeout(timer);
    };
  }, []);

  if (!progress?.active || progress.eligible === 0) return null;
  return (
    <div role="status" className="mb-4 rounded-lg border border-brand-200 bg-brand-50 p-4">
      <p className="text-sm font-semibold text-brand-950">
        Reading and comparing the shipping documents
      </p>
      <progress
        aria-label="Documents read"
        className="mt-2 h-2 w-full accent-brand-700"
        max={progress.eligible}
        value={progress.read}
      />
      <p className="mt-2 text-sm text-slate-700">
        {progress.read} of {progress.eligible} emails read · {progress.compared} compared. Results
        appear in the inbox as they finish; you can open any email meanwhile.
      </p>
    </div>
  );
}
