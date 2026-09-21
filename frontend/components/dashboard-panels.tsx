"use client";
import Link from "next/link";
import { ArrowDown, ArrowUp, GripVertical } from "lucide-react";
import { useEffect, useState, useRef } from "react";
import { api, post } from "@/lib/api/client";
import { useAuth } from "@/components/auth-provider";
import { Button, buttonVariants } from "@/components/ui/button";
import { StateChip } from "@/components/inbox/chips";
import { STATE_LABELS, STATE_ORDER } from "@/lib/inbox";
import type { InboxCounts, InboxPage } from "@/lib/api/types";
import { cn } from "@/lib/utils";

export type ExtraSummary = {
  emails_unresolved?: number; spam_count?: number; safety_held?: number; safety_assessed?: number;
  document_checks?: number; mismatches?: number; processing_failures?: number; drift_alerts_active?: number | null;
  emails_classified: number; emails_total: number;
};

type Section = "attention" | "states" | "metrics" | "guidance" | "quality";

const WIDGET_META: Record<Section, { name: string; description: string }> = {
  attention: { name: "Needs my attention", description: "The emails a person has to act on, most urgent first" },
  states: { name: "Emails by state", description: "How many emails are checked, waiting, held or need review" },
  metrics: { name: "Workload and safety", description: "Email volumes, spam detection and safety holds at a glance" },
  guidance: { name: "Review checklist", description: "Step-by-step guide for reviewing shipping documents" },
  quality: { name: "Model quality and drift", description: "Classifier performance monitoring and baseline drift detection" },
};

const ALL_SECTIONS: Section[] = ["attention", "states", "metrics", "guidance", "quality"];
const DEFAULT_SECTIONS: Section[] = ALL_SECTIONS;

type Monitor = {
  state: string; reason?: string; baseline_version?: string; window_sizes?: number[];
  reviewed_sample_count?: number; reviewed_error_rate?: number | null; reviewed_error_change?: number | null;
};

export function DashboardPanels({ data }: { data: ExtraSummary }) {
  const auth = useAuth();
  const [sections, setSections] = useState<Section[]>(DEFAULT_SECTIONS);
  const [editing, setEditing] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [monitor, setMonitor] = useState<Monitor | null>(null);
  const [counts, setCounts] = useState<InboxCounts | null>(null);
  const [attention, setAttention] = useState<InboxPage | null>(null);
  const [busy, setBusy] = useState(false);
  const dragIndex = useRef<number | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    api<{ sections: Section[] }>("/dashboard/preferences", { signal: controller.signal })
      .then(v => { if (Array.isArray(v.sections)) setSections(v.sections.filter(id => id in WIDGET_META)); })
      .catch(e => { if (!controller.signal.aborted) setError(e.message); });
    api<Monitor>("/quality/monitor", { signal: controller.signal })
      .then(setMonitor)
      .catch(e => { if (!controller.signal.aborted) setError(e.message); });
    return () => controller.abort();
  }, [auth.workspace]);

  // The inbox panels only cost a request while they are switched on.
  const wantStates = sections.includes("states");
  const wantAttention = sections.includes("attention");
  useEffect(() => {
    if (!wantStates && !wantAttention) return;
    const controller = new AbortController();
    if (wantStates)
      api<InboxCounts>("/emails/counts", { signal: controller.signal })
        .then(value => setCounts(value?.by_state ? value : null))
        .catch(() => { if (!controller.signal.aborted) setCounts(null); });
    if (wantAttention)
      api<InboxPage>("/emails?attention=true&limit=6", { signal: controller.signal })
        .then(value => {
          // A panel must never take the dashboard down: keep only well-formed rows.
          const items = Array.isArray(value?.items) ? value.items.filter(item => item?.state && item.action && item.display_id) : [];
          setAttention(Array.isArray(value?.items) ? { ...value, items } : null);
        })
        .catch(() => { if (!controller.signal.aborted) setAttention(null); });
    return () => controller.abort();
  }, [wantStates, wantAttention, auth.workspace]);

  async function save() {
    setBusy(true); setError("");
    try { await post("/dashboard/preferences", { sections }); setEditing(false); setNotice("Dashboard view saved."); }
    catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  }

  async function baseline() {
    setBusy(true); setError("");
    try { await post("/quality/baseline", {}); setMonitor(await api<Monitor>("/quality/monitor")); }
    catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  }

  function toggleSection(id: Section, on: boolean) {
    setSections(old => on ? [...old, id] : old.filter(v => v !== id));
  }
  function move(index: number, by: -1 | 1) {
    setSections(old => {
      const to = index + by;
      if (to < 0 || to >= old.length) return old;
      const next = [...old];
      [next[index], next[to]] = [next[to], next[index]];
      return next;
    });
  }

  function handleDragStart(index: number) { dragIndex.current = index; }
  function handleDragOver(e: React.DragEvent, index: number) {
    e.preventDefault();
    const from = dragIndex.current;
    if (from === null || from === index) return;
    setSections(old => {
      const next = [...old];
      const [moved] = next.splice(from, 1);
      next.splice(index, 0, moved);
      return next;
    });
    dragIndex.current = index;
  }
  function handleDragEnd() { dragIndex.current = null; }

  const metrics: [string, number | undefined | null, string][] = [
    ["Classified emails", data.emails_classified, "/inbox"],
    ["Unresolved emails", data.emails_unresolved, "/inbox?category=unclassified"],
    ["Document checks", data.document_checks, "/inbox?state=checked"],
    ["Cases with differences", data.mismatches, "/inbox?state=mismatch_found"],
    ["Failed processing jobs", data.processing_failures, "/inbox?state=needs_review"],
    ["Spam classifications", data.spam_count, "/inbox?state=spam"],
    ["Held for safety review", data.safety_held, "/inbox?state=held"],
    ["Active drift alerts", data.drift_alerts_active, "/alerts"],
  ];

  return (
    <div className="mt-8">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-xl font-semibold">Workspace details</h2>
        <Button
          variant="secondary"
          aria-expanded={editing}
          onClick={() => setEditing(v => !v)}
          tip={{ name: "Customize dashboard", description: "Choose which panels appear and in what order" }}
        >
          {editing ? "Close customization" : "Customize dashboard"}
        </Button>
      </div>

      {editing && (
        <section className="card mt-4 p-5" aria-label="Dashboard customization">
          <h3 className="mb-1 font-semibold text-slate-800">Choose and reorder panels</h3>
          <p className="mb-4 text-xs text-slate-600">Tick a panel to show it. Use the arrows, or drag a row, to change the order.</p>

          <fieldset>
            <legend className="sr-only">Panels to show</legend>
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {ALL_SECTIONS.map(id => {
                const meta = WIDGET_META[id];
                const enabled = sections.includes(id);
                return (
                  <label
                    key={id}
                    className={cn(
                      "flex cursor-pointer items-start gap-3 rounded-lg border-2 p-4",
                      enabled ? "border-brand-400 bg-brand-50" : "border-slate-200 bg-slate-50",
                    )}
                  >
                    <input
                      type="checkbox"
                      className="mt-1 size-4 accent-brand-800"
                      checked={enabled}
                      onChange={e => toggleSection(id, e.target.checked)}
                    />
                    <span>
                      <span className="block text-sm font-semibold text-slate-800">{meta.name}</span>
                      <span className="mt-0.5 block text-xs text-slate-600">{meta.description}</span>
                    </span>
                  </label>
                );
              })}
            </div>
          </fieldset>

          {sections.length > 0 && (
            <div className="mt-4">
              <p className="mb-2 text-xs font-semibold text-slate-700">Display order</p>
              <ol className="space-y-1">
                {sections.map((id, i) => {
                  const meta = WIDGET_META[id];
                  return (
                    <li
                      key={id}
                      draggable
                      onDragStart={() => handleDragStart(i)}
                      onDragOver={e => handleDragOver(e, i)}
                      onDragEnd={handleDragEnd}
                      className="flex items-center gap-2 rounded-md border border-slate-200 bg-white px-3 py-1.5 hover:shadow-sm"
                    >
                      <GripVertical aria-hidden className="size-4 cursor-grab text-slate-400" />
                      <span className="text-sm font-medium text-slate-800">{meta.name}</span>
                      <span className="ml-auto flex items-center gap-1">
                        <span className="mr-2 text-xs text-slate-600">#{i + 1}</span>
                        <Button
                          variant="secondary"
                          size="icon"
                          disabled={i === 0}
                          onClick={() => move(i, -1)}
                          aria-label={`Move ${meta.name} up`}
                          tip={{ name: "Move up", description: `Shows ${meta.name} earlier on the dashboard`, side: "left" }}
                        >
                          <ArrowUp aria-hidden className="size-4" />
                        </Button>
                        <Button
                          variant="secondary"
                          size="icon"
                          disabled={i === sections.length - 1}
                          onClick={() => move(i, 1)}
                          aria-label={`Move ${meta.name} down`}
                          tip={{ name: "Move down", description: `Shows ${meta.name} later on the dashboard`, side: "left" }}
                        >
                          <ArrowDown aria-hidden className="size-4" />
                        </Button>
                      </span>
                    </li>
                  );
                })}
              </ol>
            </div>
          )}

          <div className="mt-4 flex gap-2">
            <Button
              disabled={busy}
              onClick={save}
              tip={{ name: "Save view", description: "Keeps this layout for you in this workspace" }}
            >
              Save view
            </Button>
            <Button
              variant="secondary"
              onClick={() => setSections(DEFAULT_SECTIONS)}
              tip={{ name: "Reset to default", description: "Shows every panel in the standard order" }}
            >
              Reset to default
            </Button>
          </div>
        </section>
      )}

      {error && <p role="alert" className="mt-3 rounded-md bg-red-50 p-3 text-sm text-red-800">{error}</p>}
      {notice && <p role="status" className="mt-3 text-sm text-brand-800">{notice}</p>}

      {sections.map(id => {
        const meta = WIDGET_META[id];
        return (
          <section key={id} className="card mt-5 p-5" aria-label={meta.name}>
            <h3 className="mb-4 text-lg font-semibold text-slate-900">{meta.name}</h3>

            {id === "attention" && (
              attention === null ? (
                <p className="text-sm text-slate-600">The list of emails needing attention is unavailable. Use Refresh to retry.</p>
              ) : attention.items.length === 0 ? (
                <p className="text-sm text-slate-700">Nothing needs a person right now.</p>
              ) : (
                <>
                  <ul className="divide-y divide-slate-200">
                    {attention.items.map(item => (
                      <li key={item.id} className="py-2.5">
                        <Link href={`/inbox/${item.id}`} className="block">
                          <span className="flex flex-wrap items-center gap-2">
                            <span className="font-mono text-xs font-semibold text-slate-700">{item.display_id}</span>
                            <StateChip state={item.state} label={item.state_label} />
                          </span>
                          <span className="mt-1 block truncate text-sm font-medium text-slate-900">{item.subject}</span>
                          <span className="block text-xs text-slate-700">Next: {item.action.title}</span>
                        </Link>
                      </li>
                    ))}
                  </ul>
                  <p className="mt-3 text-xs text-slate-700">
                    Showing {attention.items.length} of {attention.total}.{" "}
                    <Link href="/inbox?state=needs_review" className="underline">Open the inbox</Link>
                  </p>
                </>
              )
            )}

            {id === "states" && (
              counts?.by_state ? (
                <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                  {STATE_ORDER.map(state => (
                    <li key={state}>
                      <Link
                        href={`/inbox?state=${state}`}
                        className="flex items-center justify-between gap-3 rounded-lg border border-slate-200 p-3 hover:border-brand-300 hover:shadow-sm"
                      >
                        <StateChip state={state} label={STATE_LABELS[state]} />
                        <strong className="text-xl text-slate-900">{(counts.by_state[state] ?? 0).toLocaleString()}</strong>
                      </Link>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-sm text-slate-600">State counts are unavailable. Use Refresh to retry.</p>
              )
            )}

            {id === "metrics" && (
              <>
                <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                  {metrics.map(([metricLabel, value, href]) => (
                    <Link
                      key={metricLabel}
                      href={href}
                      className="rounded-lg border border-slate-200 p-4 transition-all hover:border-brand-300 hover:shadow-sm"
                    >
                      <span className="text-sm text-slate-600">{metricLabel}</span>
                      <strong className="mt-2 block text-2xl font-bold text-slate-900">
                        {value == null ? "—" : value.toLocaleString()}
                      </strong>
                    </Link>
                  ))}
                </div>
                <p className="mt-3 text-xs text-slate-600">
                  Safety assessed: {data.safety_assessed ?? "—"} of {data.emails_total} emails.
                </p>
              </>
            )}

            {id === "guidance" && (
              <ol className="list-decimal space-y-3 pl-5 text-sm text-slate-700">
                <li><strong>Open the email</strong> — confirm the shipping instructions and draft bill of lading belong to this email.</li>
                <li><strong>Check the classification</strong> — rules decide first; AI is used only when you ask for it.</li>
                <li><strong>Inspect extracted fields</strong> — review the seven field values and their source quotes.</li>
                <li><strong>Resolve differences</strong> — open the comparison case and address any mismatches.</li>
                <li><strong>Verify the returned draft</strong> — confirm the corrected BL matches the SI.</li>
              </ol>
            )}

            {id === "quality" && (
              <>
                <div className="mb-3 flex items-center gap-2">
                  <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold ${
                    monitor?.state === "clear" ? "bg-green-100 text-green-900"
                    : monitor?.state === "drift_detected" ? "bg-red-100 text-red-900"
                    : "bg-slate-100 text-slate-700"
                  }`}>
                    {monitor?.state?.replaceAll("_", " ") || "Unavailable"}
                  </span>
                  <span className="text-sm text-slate-700">Drift monitoring state</span>
                </div>
                <p className="text-sm text-slate-700">
                  {monitor?.reason || "A reviewed baseline and two separate windows of 20 new classifications are required. Distribution shift does not establish concept drift."}
                </p>
                {monitor?.baseline_version && (
                  <p className="mt-2 break-all text-xs text-slate-600">Baseline: {monitor.baseline_version}</p>
                )}
                {monitor?.window_sizes && (
                  <p className="text-xs text-slate-600">Window sizes: {monitor.window_sizes.join(" / ")}</p>
                )}
                <p className="mt-2 text-xs text-slate-700">
                  Reviewed error rate:{" "}
                  {monitor?.reviewed_error_rate == null
                    ? "Insufficient reviewed labels"
                    : `${(monitor.reviewed_error_rate * 100).toFixed(1)}% from ${monitor.reviewed_sample_count} reviews`}
                </p>
                <div className="mt-4 flex flex-wrap gap-2">
                  {["reviewer","admin"].includes(auth.role || "") && (
                    <Button
                      variant="secondary"
                      disabled={busy}
                      onClick={baseline}
                      tip={{ name: "Create baseline", description: "Records today's reviewed labels as the reference for drift checks" }}
                    >
                      Create baseline from reviewed labels
                    </Button>
                  )}
                  <Link href="/alerts" className={buttonVariants({ variant: "secondary" })}>
                    Inspect alerts
                  </Link>
                </div>
              </>
            )}
          </section>
        );
      })}
    </div>
  );
}
