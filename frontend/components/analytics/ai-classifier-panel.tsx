"use client";

import { useCallback, useEffect, useState } from "react";
import { api, post } from "@/lib/api/client";
import { useAuth } from "@/components/auth-provider";
import { AiUsageText, type AiUsageData } from "@/components/ai-usage";
import { Button } from "@/components/ui/button";
import { CATEGORY_LABELS } from "@/lib/inbox";

type Metrics = {
  sample_size: number;
  rules: { correct: number; abstained: number; wrong: number; accuracy: number | null; accuracy_when_decided: number | null };
  ai: {
    asked: number; correct: number; wrong: number; unusable: number; accuracy: number | null; unusable_rate: number | null;
    latency_seconds: { mean: number | null; p95: number | null; max: number | null };
  };
  combined: { correct: number; undecided: number; accuracy: number | null };
  per_category: Record<string, { total: number; rules_correct: number; ai_correct: number }>;
};
type Run = {
  id: string; source: "heldout_cached" | "heldout_live"; status: "running" | "complete" | "failed";
  sample_size: number; calls_made: number; metrics: Metrics | Record<string, never>; error: string | null;
  created_at: string; finished_at: string | null;
};
type Overview = {
  available: boolean; message: string | null; provider_configured: boolean; latest: Run | null; usage: AiUsageData;
  plan: { sample_size: number; answered: number; to_call: number; estimated_seconds: number } | null;
};

const percent = (value: number | null | undefined) => (value == null ? "—" : `${(value * 100).toFixed(1)}%`);
const seconds = (value: number | null | undefined) => (value == null ? "—" : `${value.toFixed(1)} s`);

function Score({ title, value, detail }: { title: string; value: string; detail: string }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4">
      <p className="text-xs font-semibold uppercase tracking-wider text-slate-700">{title}</p>
      <p className="mt-2 text-3xl font-bold text-slate-900">{value}</p>
      <p className="mt-1 text-xs text-slate-700">{detail}</p>
    </div>
  );
}

export function AiClassifierPanel() {
  const auth = useAuth();
  const isAdmin = auth.role === "admin";
  const [overview, setOverview] = useState<Overview | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [understood, setUnderstood] = useState(false);

  const load = useCallback(async (signal?: AbortSignal) => {
    try {
      const value = await api<Overview>("/quality/ai-classifier", { signal });
      if (!signal?.aborted) setOverview(value);
    } catch (failure) {
      if (!signal?.aborted) setError((failure as Error).message);
    }
  }, []);
  useEffect(() => {
    const controller = new AbortController();
    void load(controller.signal);
    return () => controller.abort();
  }, [load]);

  // A live run finishes in the background: check back until it does.
  const running = overview?.latest?.status === "running";
  useEffect(() => {
    if (!running) return;
    const timer = setInterval(() => void load(), 5000);
    return () => clearInterval(timer);
  }, [running, load]);

  async function evaluate(mode: "cached" | "live") {
    setBusy(true);
    setError("");
    try {
      await post("/quality/ai-classifier/evaluate", {
        mode,
        confirm_calls: mode === "live" ? (overview?.plan?.to_call ?? 0) : 0,
      });
      setConfirming(false);
      setUnderstood(false);
      await load();
    } catch (failure) {
      setError((failure as Error).message);
    } finally {
      setBusy(false);
    }
  }

  const run = overview?.latest;
  const metrics = run?.status === "complete" ? (run.metrics as Metrics) : null;
  const plan = overview?.plan;
  const usage = overview?.usage;
  return (
    <section aria-labelledby="ai-score-heading" className="card mt-6 p-6">
      <h2 id="ai-score-heading" className="text-base font-semibold text-slate-900">AI classifier score</h2>
      <p className="mt-1 text-xs text-slate-700">
        Measured on labelled emails that were written separately from the supplied sample, so it shows how the
        classifier copes with wording it has not seen. Rules alone, the AI alone, and rules first with the AI for
        what the rules cannot decide.
      </p>
      {error && <p role="alert" className="mt-3 rounded-md bg-red-50 p-3 text-sm text-red-800">{error}</p>}

      {!overview ? (
        !error && <p role="status" className="mt-4 text-sm text-slate-700">Loading the AI score…</p>
      ) : !overview.available ? (
        <p className="mt-4 text-sm text-slate-700">{overview.message}</p>
      ) : (
        <>
          {run?.status === "running" && (
            <p role="status" className="mt-4 rounded-md bg-brand-50 p-3 text-sm text-brand-900">
              A live evaluation is running. This page updates when it finishes.
            </p>
          )}
          {run?.status === "failed" && (
            <p role="alert" className="mt-4 rounded-md bg-yellow-50 p-3 text-sm text-yellow-900">
              The last run stopped: {run.error ?? "unknown reason"}. Scores below are from what was answered.
            </p>
          )}
          {metrics ? (
            <>
              <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-3">
                <Score
                  title="Rules alone"
                  value={percent(metrics.rules.accuracy)}
                  detail={`${metrics.rules.correct} of ${metrics.sample_size} right, ${metrics.rules.abstained} left undecided`}
                />
                <Score
                  title="AI alone"
                  value={percent(metrics.ai.accuracy)}
                  detail={`${metrics.ai.correct} of ${metrics.ai.asked} right, ${metrics.ai.unusable} unusable answers`}
                />
                <Score
                  title="Rules, then AI"
                  value={percent(metrics.combined.accuracy)}
                  detail={`${metrics.combined.correct} of ${metrics.sample_size} right, ${metrics.combined.undecided} undecided`}
                />
              </div>
              <dl className="mt-4 grid grid-cols-2 gap-x-6 gap-y-2 text-sm sm:grid-cols-4">
                {[
                  ["Sample size", `${metrics.sample_size} emails`],
                  ["Unusable AI output", percent(metrics.ai.unusable_rate)],
                  ["AI latency (mean / p95)", `${seconds(metrics.ai.latency_seconds.mean)} / ${seconds(metrics.ai.latency_seconds.p95)}`],
                  ["Live calls in this run", String(run?.calls_made ?? 0)],
                ].map(([term, value]) => (
                  <div key={term}>
                    <dt className="text-xs text-slate-700">{term}</dt>
                    <dd className="font-semibold text-slate-900">{value}</dd>
                  </div>
                ))}
              </dl>
              <div className="mt-4 overflow-x-auto">
                <table className="w-full min-w-[26rem] text-sm">
                  <caption className="sr-only">Correct classifications by category</caption>
                  <thead>
                    <tr className="border-b border-slate-300 text-left text-xs text-slate-700">
                      <th scope="col" className="py-1.5 pr-3 font-semibold">Category</th>
                      <th scope="col" className="px-3 py-1.5 font-semibold">Emails</th>
                      <th scope="col" className="px-3 py-1.5 font-semibold">Rules right</th>
                      <th scope="col" className="px-3 py-1.5 font-semibold">AI right</th>
                    </tr>
                  </thead>
                  <tbody>
                    {Object.entries(metrics.per_category).map(([category, row]) => (
                      <tr key={category} className="border-b border-slate-200">
                        <th scope="row" className="py-1.5 pr-3 text-left font-medium text-slate-800">{CATEGORY_LABELS[category] ?? category}</th>
                        <td className="px-3 py-1.5">{row.total}</td>
                        <td className="px-3 py-1.5">{row.rules_correct}</td>
                        <td className="px-3 py-1.5">{row.ai_correct}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <p className="mt-3 text-xs text-slate-700">
                {run?.source === "heldout_live" ? "From a live run" : "Scored from AI answers saved earlier, with no new calls"}
                {run?.finished_at ? `, ${new Date(run.finished_at).toLocaleString()}` : ""}. This is a small sample of {metrics.sample_size} emails:
                read the percentages as a guide, not a guarantee.
              </p>
            </>
          ) : (
            !running && <p className="mt-4 text-sm text-slate-700">No score has been saved yet. Scoring from saved AI answers is free.</p>
          )}

          <div className="mt-5 flex flex-wrap items-center gap-3 border-t border-slate-200 pt-4">
            {usage && (
              <p className="mr-auto text-xs text-slate-700">
                <AiUsageText usage={usage} />
              </p>
            )}
            <Button
              variant="secondary"
              disabled={!isAdmin || busy || running}
              onClick={() => void evaluate("cached")}
              tip={{ name: "Refresh score", description: "Re-scores from AI answers already saved; makes no AI calls" }}
            >
              Refresh score (no AI calls)
            </Button>
            <Button
              variant="secondary"
              disabled={!isAdmin || busy || running || !plan || plan.to_call === 0 || !overview.provider_configured}
              onClick={() => setConfirming((value) => !value)}
              aria-expanded={confirming}
              tip={{
                name: "Run live evaluation",
                description: !isAdmin
                  ? "Only an administrator can start this"
                  : plan?.to_call === 0
                    ? "Every email already has an AI answer, so a live run would make no calls"
                    : !overview.provider_configured
                      ? "No AI provider is configured"
                      : "Asks the AI provider for the emails that have no saved answer",
              }}
            >
              Run live evaluation
            </Button>
          </div>

          {confirming && plan && usage && (
            <div role="group" aria-label="Confirm live evaluation" className="mt-3 rounded-lg border border-yellow-400 bg-yellow-50 p-4 text-sm text-yellow-900">
              <p>
                This will ask the AI provider <strong>{plan.to_call} times</strong>, about {Math.ceil(plan.estimated_seconds / 60)} minutes,
                and uses {plan.to_call} of the {usage.remaining} calls left {usage.scope === "demo_session" ? "in this demo session" : "today"}.
                Emails that already have an answer are not sent again.
              </p>
              {plan.to_call > usage.remaining && (
                <p role="alert" className="mt-2 font-semibold">There are not enough calls left in the budget to run this.</p>
              )}
              <label className="mt-3 flex items-center gap-2">
                <input type="checkbox" className="size-4 accent-brand-800" checked={understood} onChange={(event) => setUnderstood(event.target.checked)} />
                I understand this uses {plan.to_call} AI calls
              </label>
              <Button
                className="mt-3"
                disabled={!understood || busy || plan.to_call > usage.remaining}
                onClick={() => void evaluate("live")}
              >
                Start {plan.to_call} AI calls
              </Button>
            </div>
          )}
        </>
      )}
    </section>
  );
}
