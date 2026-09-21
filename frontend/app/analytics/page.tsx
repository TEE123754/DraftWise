"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import {
  Activity,
  BarChart3,
  CheckCircle2,
  Cpu,
  Layers,
  Sparkles,
  TrendingUp,
} from "lucide-react";
import { api } from "@/lib/api/client";
import { AiClassifierPanel } from "@/components/analytics/ai-classifier-panel";
import { label } from "@/lib/utils";

type Scoreboard = {
  final_score: number;
  stage1: { accuracy: number };
  stage3: { defect_precision: number; defect_recall: number };
  end_to_end: { success: number; total: number };
  reliability: { escalation_precision: number; pred_review: number; gold_review: number };
};

type BenchmarkData = {
  official: {
    scoreboard: Scoreboard;
    run: string;
    emails: number | null;
    unresolved: number;
    ai_fallback: boolean | null;
  } | null;
  reference: { source: string; independent: boolean };
  provider: {
    name: string;
    model: string;
    timeout_seconds: number;
    extraction_timeout_seconds: number;
  };
  dataset: {
    total_emails: number;
    reference_evaluated: number;
  };
  overall: {
    accuracy: number;
    abstention_rate: number;
    coverage: number;
  };
  by_method: {
    rule: { count: number; accuracy: number };
    ai: { count: number; accuracy: number | null };
    fallback: { count: number; accuracy: number | null };
  };
  categories: Record<
    string,
    { support: number; precision: number; recall: number; f1: number }
  >;
};

export default function AnalyticsPage() {
  const [data, setData] = useState<BenchmarkData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    api<BenchmarkData>("/quality/benchmark")
      .then(setData)
      .catch((err) => setError((err as Error).message))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="mx-auto max-w-5xl py-12 text-center text-sm text-slate-500">
        Loading quality and benchmark analytics…
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="mx-auto max-w-5xl py-8">
        <h1 className="text-3xl font-semibold text-slate-900">Model quality</h1>
        <div role="alert" className="mt-4 rounded-lg bg-red-50 p-4 text-sm text-red-800">
          {error || "Could not load benchmark metrics."}
        </div>
        <AiClassifierPanel />
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-5xl py-6">
      <header className="flex flex-col justify-between gap-4 sm:flex-row sm:items-center">
        <div>
          <h1 className="text-3xl font-semibold text-slate-900">
            Model Quality & Benchmark
          </h1>
          <p className="mt-2 text-sm text-slate-600">
            Email classification compared with reference labels for {data.dataset.reference_evaluated} sample emails.
          </p>
        </div>
        <div className="flex items-center gap-2 rounded-full border border-slate-200 bg-slate-50 px-3.5 py-1 text-xs font-semibold text-slate-700">
          <Activity size={14} className="text-slate-500" />
          Development check
        </div>
      </header>

      {data.official && (
        <section aria-labelledby="official-heading" className="card mt-6 p-6">
          <h2 id="official-heading" className="text-base font-semibold text-slate-900">
            Official self-evaluation
          </h2>
          <p className="mt-1 text-xs text-slate-500">
            Scored by the organizer scoring server on {data.official.emails ?? "all"} sample emails
            ({data.official.run}).{" "}
            {data.official.ai_fallback === false
              ? "This run used the built-in rules only, with no AI provider."
              : data.official.ai_fallback
                ? "AI extraction fallback was enabled for this run."
                : "Whether AI was used in this run was not recorded."}
            {data.official.unresolved > 0 &&
              ` ${data.official.unresolved} emails the rules could not classify were left out of the submission and so could not score.`}{" "}
            A result on the supplied sample says little about unseen mail: expect lower scores on
            different wording and layouts.
          </p>
          <dl className="mt-4 grid grid-cols-2 gap-4 sm:grid-cols-5">
            <div>
              <dt className="text-xs uppercase tracking-wider text-slate-500">Final score</dt>
              <dd className="mt-1 text-2xl font-bold text-slate-900">
                {data.official.scoreboard.final_score.toFixed(3)}
              </dd>
            </div>
            <div>
              <dt className="text-xs uppercase tracking-wider text-slate-500">Classification</dt>
              <dd className="mt-1 text-2xl font-bold text-slate-900">
                {(data.official.scoreboard.stage1.accuracy * 100).toFixed(1)}%
              </dd>
            </div>
            <div>
              <dt className="text-xs uppercase tracking-wider text-slate-500">Defect precision / recall</dt>
              <dd className="mt-1 text-2xl font-bold text-slate-900">
                {(data.official.scoreboard.stage3.defect_precision * 100).toFixed(0)}% /{" "}
                {(data.official.scoreboard.stage3.defect_recall * 100).toFixed(0)}%
              </dd>
            </div>
            <div>
              <dt className="text-xs uppercase tracking-wider text-slate-500">Defects caught exactly</dt>
              <dd className="mt-1 text-2xl font-bold text-slate-900">
                {data.official.scoreboard.end_to_end.success} / {data.official.scoreboard.end_to_end.total}
              </dd>
            </div>
            <div>
              <dt className="text-xs uppercase tracking-wider text-slate-500">Review precision</dt>
              <dd className="mt-1 text-2xl font-bold text-slate-900">
                {(data.official.scoreboard.reliability.escalation_precision * 100).toFixed(0)}%
              </dd>
              <dd className="text-xs text-slate-500">
                {data.official.scoreboard.reliability.pred_review} sent, {data.official.scoreboard.reliability.gold_review} needed
              </dd>
            </div>
          </dl>
        </section>
      )}

      <AiClassifierPanel />

      {/* Agreement of the rules pipeline with this project's own report: a regression check, not an accuracy */}
      <section aria-labelledby="ai-benchmark-heading" className="card mt-6 p-6">
        <div className="flex items-center gap-2 mb-1">
          <Sparkles size={18} className="text-amber-500" />
          <h2 id="ai-benchmark-heading" className="text-base font-semibold text-slate-900">
            Agreement with the project&apos;s own report
          </h2>
        </div>
        <p className="text-xs text-slate-500 mb-5">
          {data.reference?.independent
            ? `Compared with ${data.dataset.reference_evaluated} independently reviewed labels.`
            : `Compared with ${data.dataset.reference_evaluated} results from this project's own generated report, which is not an independent answer key. It catches regressions; it is not a measure of accuracy.`}
        </p>

        {/* Score cards */}
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-4 mb-6">
          <div className="rounded-lg border border-brand-200 bg-brand-50 p-4">
            <p className="text-xs font-medium uppercase tracking-wider text-brand-600">Overall Accuracy</p>
            <p className="mt-2 text-3xl font-bold text-brand-900">
              {(data.overall.accuracy * 100).toFixed(2)}%
            </p>
            <p className="mt-1 text-xs text-brand-700">{data.dataset.reference_evaluated} emails evaluated</p>
          </div>
          <div className="rounded-lg border border-emerald-200 bg-emerald-50 p-4">
            <p className="text-xs font-medium uppercase tracking-wider text-emerald-600">Coverage</p>
            <p className="mt-2 text-3xl font-bold text-emerald-900">
              {(data.overall.coverage * 100).toFixed(1)}%
            </p>
            <p className="mt-1 text-xs text-emerald-700">
              {data.by_method.fallback.count === 0 ? "0 abstentions" : `${data.by_method.fallback.count} abstentions`}
            </p>
          </div>
          <div className="rounded-lg border border-indigo-200 bg-indigo-50 p-4">
            <p className="text-xs font-medium uppercase tracking-wider text-indigo-600">Rule Hits</p>
            <p className="mt-2 text-3xl font-bold text-indigo-900">{data.by_method.rule.count}</p>
            <p className="mt-1 text-xs text-indigo-700">
              {(data.by_method.rule.accuracy * 100).toFixed(1)}% accuracy
            </p>
          </div>
          <div className="rounded-lg border border-amber-200 bg-amber-50 p-4">
            <p className="text-xs font-medium uppercase tracking-wider text-amber-600">AI-Assisted</p>
            <p className="mt-2 text-3xl font-bold text-amber-900">{data.by_method.ai.count}</p>
            <p className="mt-1 text-xs text-amber-700">
              {data.by_method.ai.accuracy != null
                ? `${(data.by_method.ai.accuracy * 100).toFixed(1)}% accuracy`
                : "Rule fallback only"}
            </p>
          </div>
        </div>

        {/* Side-by-side comparison when organizer score is available */}
        {data.official && (
          <div className="rounded-lg border border-slate-200 bg-slate-50 p-4">
            <p className="text-xs font-semibold text-slate-600 mb-3">Score Comparison</p>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <p className="text-xs text-slate-500 mb-1">Organizer Score (Classification Stage)</p>
                <p className="text-2xl font-bold text-slate-900">
                  {(data.official.scoreboard.stage1.accuracy * 100).toFixed(1)}%
                </p>
                <p className="text-xs text-slate-400">From organizer scoring server</p>
              </div>
              <div>
                <p className="text-xs text-slate-500 mb-1">Agreement with own report</p>
                <p className="text-2xl font-bold text-brand-800">
                  {(data.overall.accuracy * 100).toFixed(2)}%
                </p>
                <p className="text-xs text-slate-400">Agreement with the project&apos;s own report</p>
              </div>
            </div>
          </div>
        )}
      </section>

      <h2 className="mt-8 text-base font-semibold text-slate-900">
        Classifier agreement (regression check)
      </h2>

      {!data.reference.independent && (
        <p role="note" className="mt-4 rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
          The reference labels ({data.reference.source}) come from an earlier
          run of this project&apos;s own pipeline, not an independent answer key.
          These figures show agreement, which catches regressions; they are not
          measured accuracy.
        </p>
      )}

      {/* Top 4 Metric Cards */}
      <div className="mt-6 grid grid-cols-1 gap-4 sm:grid-cols-4">
        <div className="card p-5">
          <div className="flex items-center justify-between text-slate-500">
            <span className="text-xs font-medium uppercase tracking-wider">Reference agreement</span>
            <TrendingUp size={18} className="text-brand-600" />
          </div>
          <p className="mt-2 text-3xl font-bold text-slate-900">
            {(data.overall.accuracy * 100).toFixed(1)}%
          </p>
          <p className="mt-1 text-xs text-slate-500">
            Across {data.dataset.reference_evaluated} compared emails
          </p>
        </div>

        <div className="card p-5">
          <div className="flex items-center justify-between text-slate-500">
            <span className="text-xs font-medium uppercase tracking-wider">Coverage</span>
            <CheckCircle2 size={18} className="text-emerald-600" />
          </div>
          <p className="mt-2 text-3xl font-bold text-slate-900">
            {(data.overall.coverage * 100).toFixed(1)}%
          </p>
          <p className="mt-1 text-xs text-slate-500">
            {data.by_method.fallback.count === 0
              ? "No emails left unresolved"
              : `${data.by_method.fallback.count} emails left unresolved`}
          </p>
        </div>

        <div className="card p-5">
          <div className="flex items-center justify-between text-slate-500">
            <span className="text-xs font-medium uppercase tracking-wider">Rule Direct Hits</span>
            <Layers size={18} className="text-indigo-600" />
          </div>
          <p className="mt-2 text-3xl font-bold text-slate-900">
            {data.by_method.rule.count}
          </p>
          <p className="mt-1 text-xs text-slate-500">
            {(data.by_method.rule.accuracy * 100).toFixed(1)}% agreement
          </p>
        </div>

        <div className="card p-5">
          <div className="flex items-center justify-between text-slate-500">
            <span className="text-xs font-medium uppercase tracking-wider">AI-Assisted Hits</span>
            <Sparkles size={18} className="text-amber-600" />
          </div>
          <p className="mt-2 text-3xl font-bold text-slate-900">
            {data.by_method.ai.count}
          </p>
          <p className="mt-1 text-xs text-slate-500">
            {data.by_method.ai.accuracy !== null
              ? `${(data.by_method.ai.accuracy * 100).toFixed(1)}% agreement`
              : "Rule fallback"}
          </p>
        </div>
      </div>

      {/* Method Breakdown & Provider Config */}
      <div className="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-3">
        <div className="card p-6 lg:col-span-2">
          <h2 className="flex items-center gap-2 text-base font-semibold text-slate-900">
            <BarChart3 size={18} className="text-brand-700" />
            Decision Method Breakdown
          </h2>
          <p className="mt-1 text-xs text-slate-500">
            High-precision deterministic rules handle the standard taxonomy; live LLM resolves complex requests.
          </p>

          <div className="mt-5 space-y-4">
            <div>
              <div className="flex justify-between text-xs font-semibold">
                <span>Deterministic Rules</span>
                <span>
                  {data.by_method.rule.count} ({((data.by_method.rule.count / data.dataset.total_emails) * 100).toFixed(1)}%)
                </span>
              </div>
              <div className="mt-1.5 h-2.5 w-full rounded-full bg-slate-100 overflow-hidden">
                <div
                  className="h-full rounded-full bg-brand-600"
                  style={{
                    width: `${(data.by_method.rule.count / data.dataset.total_emails) * 100}%`,
                  }}
                />
              </div>
            </div>

            <div>
              <div className="flex justify-between text-xs font-semibold">
                <span>AI Classifier (Morpheus / Gemini)</span>
                <span>
                  {data.by_method.ai.count} ({((data.by_method.ai.count / data.dataset.total_emails) * 100).toFixed(1)}%)
                </span>
              </div>
              <div className="mt-1.5 h-2.5 w-full rounded-full bg-slate-100 overflow-hidden">
                <div
                  className="h-full rounded-full bg-amber-500"
                  style={{
                    width: `${(data.by_method.ai.count / data.dataset.total_emails) * 100}%`,
                  }}
                />
              </div>
            </div>

            <div>
              <div className="flex justify-between text-xs font-semibold">
                <span>Unresolved / Fallback</span>
                <span>
                  {data.by_method.fallback.count} ({(data.overall.abstention_rate * 100).toFixed(1)}%)
                </span>
              </div>
              <div className="mt-1.5 h-2.5 w-full rounded-full bg-slate-100 overflow-hidden">
                <div
                  className="h-full rounded-full bg-slate-300"
                  style={{
                    width: `${(data.by_method.fallback.count / data.dataset.total_emails) * 100}%`,
                  }}
                />
              </div>
            </div>
          </div>
        </div>

        {/* AI Provider Card */}
        <div className="card p-6">
          <h2 className="flex items-center gap-2 text-base font-semibold text-slate-900">
            <Cpu size={18} className="text-brand-700" />
            AI Provider Engine
          </h2>
          <div className="mt-4 space-y-3 text-xs">
            <div className="flex justify-between border-b border-slate-100 pb-2">
              <span className="text-slate-500">Provider:</span>
              <span className="font-semibold capitalize text-slate-900">{data.provider.name}</span>
            </div>
            <div className="flex justify-between border-b border-slate-100 pb-2">
              <span className="text-slate-500">Model:</span>
              <span className="font-semibold text-slate-900">{data.provider.model}</span>
            </div>
            <div className="flex justify-between border-b border-slate-100 pb-2">
              <span className="text-slate-500">Request timeout:</span>
              <span className="font-semibold text-slate-900">{data.provider.timeout_seconds}s</span>
            </div>
            <div className="flex justify-between border-b border-slate-100 pb-2">
              <span className="text-slate-500">Extraction timeout:</span>
              <span className="font-semibold text-slate-900">{data.provider.extraction_timeout_seconds}s</span>
            </div>
            <p className="text-slate-500">
              The current provider may differ from the one that produced these figures.
              Drift status is on the{" "}
              <Link href="/alerts" className="underline">Alerts page</Link>.
            </p>
          </div>
        </div>
      </div>

      {/* Per-Category Precision & Recall Table */}
      <section className="card mt-6 overflow-hidden">
        <div className="border-b border-slate-200 px-6 py-4">
          <h2 className="text-base font-semibold text-slate-900">
            Classification Performance by Category
          </h2>
          <p className="text-xs text-slate-500">
            Precision, recall and F1 measured against the reference labels described above.
          </p>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-slate-200 bg-slate-50 text-xs font-medium text-slate-500 uppercase">
              <tr>
                <th className="px-6 py-3">Category</th>
                <th className="px-6 py-3">Reference support</th>
                <th className="px-6 py-3">Precision</th>
                <th className="px-6 py-3">Recall</th>
                <th className="px-6 py-3">F1 Score</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {Object.entries(data.categories).map(([category, metrics]) => (
                <tr key={category} className="hover:bg-slate-50/80">
                  <td className="px-6 py-3.5 font-medium text-slate-900">
                    {label(category)}
                  </td>
                  <td className="px-6 py-3.5 text-slate-600">
                    {metrics.support}
                  </td>
                  <td className="px-6 py-3.5 font-semibold text-slate-800">
                    {(metrics.precision * 100).toFixed(1)}%
                  </td>
                  <td className="px-6 py-3.5 font-semibold text-slate-800">
                    {(metrics.recall * 100).toFixed(1)}%
                  </td>
                  <td className="px-6 py-3.5">
                    <span className="inline-flex rounded-full bg-brand-50 px-2.5 py-0.5 text-xs font-bold text-brand-800">
                      {(metrics.f1 * 100).toFixed(1)}%
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
