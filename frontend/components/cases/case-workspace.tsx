"use client";

import { DocumentActions } from "@/components/document-actions";
import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import {
  ArrowLeft,
  CheckCircle2,
  ChevronRight,
  FilePlus2,
  RefreshCw,
} from "lucide-react";
import { api, post, uploadDocument, waitForJob } from "@/lib/api/client";
import type { CaseDetail, Comparison, Preview } from "@/lib/api/types";
import { label } from "@/lib/utils";
import { useAuth } from "@/components/auth-provider";
import { Button } from "@/components/ui/button";
import { StatusBadge } from "./status-badge";
import { NextActionCard } from "./next-action-card";
import { EvidenceViewer } from "./evidence-viewer";
import { CorrectionPreview } from "./correction-preview";
import { ReturnedDraftSummary } from "./returned-draft-summary";
import { AmendmentTimeline } from "./amendment-timeline";

export function CaseWorkspace({ caseId }: { caseId: string }) {
  const auth = useAuth();
  const reviewer = ["reviewer", "admin"].includes(auth.role);
  const operator = ["operator", "reviewer", "admin"].includes(auth.role);
  const [detail, setDetail] = useState<CaseDetail | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState("");
  const [evidence, setEvidence] = useState<Comparison | null>(null);
  const [preview, setPreview] = useState<Preview | null>(null);
  const [selecting, setSelecting] = useState(false);
  const [si, setSi] = useState("");
  const [bl, setBl] = useState("");
  const fileInput = useRef<HTMLInputElement>(null);
  const load = useCallback(async () => {
    try {
      const result = await api<CaseDetail>(`/cases/${caseId}`);
      setDetail(result);
      setSi(result.active_sources.si_extraction_id || "");
      setBl(result.active_sources.bl_extraction_id || "");
    } catch (error) {
      setError((error as Error).message);
    }
  }, [caseId]);
  useEffect(() => {
    void load();
  }, [load]);
  useEffect(() => {
    setPreview(null);
    setEvidence(null);
  }, [detail?.case.version]);
  useEffect(() => {
    if (detail?.case.readiness !== "checking") return;
    const timer = setInterval(load, 2500);
    return () => clearInterval(timer);
  }, [detail?.case.readiness, load]);
  async function createPreview() {
    if (!detail?.latest_report) return;
    const mismatchFields = detail.latest_report.comparisons
      .filter((row) => row.decision === "mismatch")
      .map((row) => row.field);
    const issueIds = detail.issues
      .filter(
        (issue) =>
          issue.state === "open" &&
          issue.source_report_id === detail.latest_report!.id &&
          mismatchFields.includes(issue.field),
      )
      .map((issue) => issue.id);
    setBusy("Preparing correction preview…");
    setError("");
    try {
      setPreview(
        await post<Preview>(`/cases/${caseId}/previews`, {
          expected_version: detail.case.version,
          report_id: detail.latest_report.id,
          issue_ids: issueIds,
        }),
      );
    } catch (error) {
      setError((error as Error).message);
    } finally {
      setBusy("");
    }
  }
  async function selectSources(event: React.FormEvent) {
    event.preventDefault();
    if (!detail) return;
    setBusy("Checking the selected sources…");
    setError("");
    try {
      const result = await post<{ job_id: string }>(
        `/cases/${caseId}/sources`,
        {
          expected_version: detail.case.version,
          si_extraction_id: si,
          bl_extraction_id: bl,
          reason:
            "Reviewer confirmed these documents belong to this shipment and selected the active revisions.",
        },
      );
      setSelecting(false);
      await load();
      await waitForJob(result.job_id);
      await load();
    } catch (error) {
      setError((error as Error).message);
    } finally {
      setBusy("");
    }
  }
  async function addDraft(file: File) {
    if (!detail) return;
    setBusy("Uploading and reading the returned draft…");
    setError("");
    try {
      const attachmentId = await uploadDocument(detail.case.email_id, file);
      const result = await post<{ job_id: string }>(`/cases/${caseId}/drafts`, {
        expected_version: detail.case.version,
        attachment_id: attachmentId,
      });
      await waitForJob(result.job_id);
      await load();
      setSelecting(true);
    } catch (error) {
      setError((error as Error).message);
    } finally {
      setBusy("");
      if (fileInput.current) fileInput.current.value = "";
    }
  }
  async function retryCheck() {
    if (!detail?.current_job || !operator) return;
    setBusy("Retrying the document check…");
    setError("");
    try {
      const result = await post<{ job_id: string }>(
        `/jobs/${detail.current_job.id}/retry`,
        {
          reason:
            "Operator retried the failed document check from the case workspace.",
        },
      );
      await load();
      await waitForJob(result.job_id);
    } catch (error) {
      setError((error as Error).message);
    } finally {
      await load();
      setBusy("");
    }
  }
  function continueAction() {
    if (!detail) return;
    switch (detail.case.next_action.kind) {
      case "request_si":
      case "request_bl":
      case "request_both":
      case "resend":
      case "await_draft":
        document
          .querySelector<HTMLElement>('[aria-label="Document follow-up"]')
          ?.focus();
        break;
      case "retry":
        void retryCheck();
        break;
      case "preview_corrections":
        void createPreview();
        break;
      case "add_draft":
        fileInput.current?.click();
        break;
      case "review_evidence":
        setEvidence(
          detail.latest_report?.comparisons.find(
            (row) => row.field === detail.case.next_action.fields[0],
          ) || null,
        );
        break;
      default:
        setSelecting(true);
    }
  }
  if (!detail)
    return (
      <div>
        <Link href="/cases" className="text-sm text-brand-800">
          ← Back to queue
        </Link>
        <p role={error ? "alert" : "status"} className="mt-6">
          {error || "Loading case…"}
        </p>
        {error && (
          <Button onClick={load} className="mt-4">
            Try again
          </Button>
        )}
      </div>
    );
  const currentSources = detail.latest_report?.comparisons.every(
    (row) =>
      row.si.extraction_id === detail.active_sources.si_extraction_id &&
      row.bl.extraction_id === detail.active_sources.bl_extraction_id,
  );
  return (
    <>
      <Link
        href="/cases"
        className="inline-flex items-center gap-2 text-sm text-slate-500 hover:text-brand-800"
      >
        <ArrowLeft size={15} /> Attention queue
      </Link>
      <header className="mt-5 flex flex-wrap items-center justify-between gap-4">
        <div>
          <div className="flex flex-wrap items-center gap-3">
            <h1 className="text-3xl font-semibold tracking-tight">
              {detail.case.reference}
            </h1>
            <StatusBadge status={detail.case.readiness} />
          </div>
          <p className="mt-2 text-sm text-slate-500">
            Shipping instructions → draft check → correction → returned draft
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={load} aria-label="Refresh case">
            <RefreshCw size={16} />
          </Button>
          <Button
            variant="outline"
            disabled={Boolean(busy) || !operator}
            onClick={() => fileInput.current?.click()}
          >
            <FilePlus2 size={16} /> Add returned draft
          </Button>
          <input
            ref={fileInput}
            type="file"
            accept=".pdf,.txt,.docx,.xlsx"
            aria-label="Returned draft file"
            className="hidden"
            onChange={(e) => {
              const file = e.target.files?.[0];
              if (file) void addDraft(file);
            }}
          />
        </div>
      </header>
      {error && (
        <p
          role="alert"
          className="mt-5 rounded-lg bg-red-50 p-4 text-sm text-red-900"
        >
          {error}
        </p>
      )}
      {busy && (
        <p role="status" className="mt-4 text-sm text-brand-900">
          {busy}
        </p>
      )}
      <div className="mt-6">
        <DocumentActions
          emailId={detail.case.email_id}
          onChanged={load}
          refreshKey={detail.case.version}
        />
        <NextActionCard
          action={detail.case.next_action}
          onAction={continueAction}
          disabled={
            Boolean(busy) ||
            (detail.case.next_action.kind === "retry" &&
              (!operator ||
                !detail.current_job ||
                detail.current_job.attempt >= 10)) ||
            (!reviewer &&
              detail.case.next_action.kind === "preview_corrections")
          }
        />
      </div>
      <div className="mt-6 grid items-start gap-6 xl:grid-cols-[minmax(0,1fr)_280px]">
        <div className="min-w-0 space-y-5">
          {detail.rounds.length > 1 && (
            <ReturnedDraftSummary round={detail.rounds[0]} />
          )}
          <section className="card p-5">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <h2 className="font-semibold">Pinned source documents</h2>
                <p className="mt-1 text-xs text-slate-500">
                  Confirm the shipment and revision before running a check.
                </p>
              </div>
              <Button
                variant="ghost"
                disabled={!reviewer || Boolean(busy)}
                onClick={() => setSelecting(!selecting)}
              >
                {selecting ? "Cancel selection" : "Choose sources"}
              </Button>
            </div>
            {selecting ? (
              <form onSubmit={selectSources} className="mt-4 space-y-4">
                <div>
                  <label htmlFor="si-source" className="text-sm font-medium">
                    Authoritative shipping instructions
                  </label>
                  <select
                    id="si-source"
                    required
                    className="input mt-1"
                    value={si}
                    onChange={(e) => setSi(e.target.value)}
                  >
                    <option value="">Select SI</option>
                    {detail.available_sources
                      .filter((source) => source.document_type === "SI")
                      .map((source) => (
                        <option value={source.id} key={source.id}>
                          {source.original_name} · revision {source.revision}
                        </option>
                      ))}
                  </select>
                </div>
                <div>
                  <label htmlFor="bl-source" className="text-sm font-medium">
                    Draft bill of lading to check
                  </label>
                  <select
                    id="bl-source"
                    required
                    className="input mt-1"
                    value={bl}
                    onChange={(e) => setBl(e.target.value)}
                  >
                    <option value="">Select draft BL</option>
                    {detail.available_sources
                      .filter((source) => source.document_type === "BL")
                      .map((source) => (
                        <option value={source.id} key={source.id}>
                          {source.original_name} · revision {source.revision}
                        </option>
                      ))}
                  </select>
                </div>
                <p className="text-xs text-slate-500">
                  Changing the instructions starts a new baseline and
                  invalidates prior correction previews.
                </p>
                <Button disabled={Boolean(busy) || !si || !bl}>
                  Confirm sources and check
                </Button>
              </form>
            ) : (
              <div className="mt-4 grid gap-3 sm:grid-cols-2">
                {[
                  [
                    "Shipping instructions",
                    detail.active_sources.si_extraction_id,
                  ],
                  [
                    "Draft bill of lading",
                    detail.active_sources.bl_extraction_id,
                  ],
                ].map(([title, id]) => (
                  <div key={title} className="rounded-lg bg-slate-50 p-3">
                    <p className="text-xs text-slate-500">{title}</p>
                    <p className="mt-1 break-words text-sm font-medium">
                      {detail.available_sources.find(
                        (source) => source.id === id,
                      )?.original_name || "Not selected"}
                    </p>
                  </div>
                ))}
              </div>
            )}
            {!detail.available_sources.length && (
              <p className="mt-4 text-sm text-slate-600">
                Add and process the SI and BL from the{" "}
                <Link
                  className="underline"
                  href={`/inbox/${detail.case.email_id}`}
                >
                  original email
                </Link>
                .
              </p>
            )}
          </section>
          {detail.latest_report && (
            <section className="card overflow-hidden">
              <div className="border-b p-5">
                <h2 className="font-semibold">Seven-field comparison</h2>
                <p className="mt-1 text-xs text-slate-500">
                  Select a field to inspect the exact source evidence.
                </p>
                {!currentSources && (
                  <p role="status" className="mt-2 text-sm text-amber-900">
                    This is the previous check. The newly selected documents are
                    still being checked.
                  </p>
                )}
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-left text-sm">
                  <caption className="sr-only">
                    Shipping instructions compared with the draft bill of lading
                  </caption>
                  <thead className="bg-slate-50 text-xs text-slate-500">
                    <tr>
                      <th className="px-5 py-3">Field</th>
                      <th className="px-4 py-3">SI</th>
                      <th className="px-4 py-3">Draft BL</th>
                      <th className="px-4 py-3">Result</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {detail.latest_report.comparisons.map((row) => (
                      <tr
                        key={row.field}
                        className={
                          row.decision === "match" ? "" : "bg-amber-50/40"
                        }
                      >
                        <th className="min-w-40 px-5 py-4 font-medium">
                          <Button
                            variant="link"
                            onClick={() => setEvidence(row)}
                            className="text-left font-medium capitalize text-brand-900"
                            tip={{ name: label(row.field), description: "Shows the source quotes behind this field", side: "right" }}
                          >
                            {label(row.field)}
                          </Button>
                        </th>
                        <td className="max-w-52 px-4 py-4">
                          {row.si.raw || (
                            <span className="text-slate-500">Missing</span>
                          )}
                        </td>
                        <td className="max-w-52 px-4 py-4">
                          {row.bl.raw || (
                            <span className="text-slate-500">Missing</span>
                          )}
                        </td>
                        <td className="px-4 py-4">
                          <span
                            className={`inline-flex items-center gap-1 whitespace-nowrap text-xs font-semibold ${row.decision === "match" ? "text-brand-800" : "text-amber-900"}`}
                          >
                            {row.decision === "match" && (
                              <CheckCircle2 size={14} />
                            )}
                            {row.decision === "match"
                              ? "Matches"
                              : row.decision === "mismatch"
                                ? "Change needed"
                                : "Review needed"}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          )}
          {evidence && (
            <EvidenceViewer
              comparison={evidence}
              sources={detail.available_sources}
              review={
                reviewer &&
                currentSources &&
                detail.case.readiness !== "checking"
                  ? { caseId, version: detail.case.version, onSaved: load }
                  : undefined
              }
              onClose={() => setEvidence(null)}
            />
          )}
          {detail.latest_report?.comparisons.some(
            (row) => row.decision === "mismatch",
          ) &&
            !preview && (
              <Button
                disabled={!reviewer || Boolean(busy) || !currentSources}
                onClick={createPreview}
              >
                Preview supported corrections <ChevronRight size={16} />
              </Button>
            )}
          {preview && (
            <CorrectionPreview
              key={preview.id}
              preview={preview}
              caseId={caseId}
              onClose={() => setPreview(null)}
              onShared={() => {
                setPreview(null);
                void load();
              }}
            />
          )}
        </div>
        <aside
          aria-label="Case history and correspondence"
          className="space-y-5"
        >
          <AmendmentTimeline rounds={detail.rounds} />
          <div className="card p-5">
            <h2 className="font-semibold">Original correspondence</h2>
            <p className="mt-2 text-sm text-slate-500">
              Keep the request and attachments within reach.
            </p>
            <Link
              href={`/inbox/${detail.case.email_id}`}
              className="mt-3 inline-flex items-center gap-1 text-sm font-semibold text-brand-800"
            >
              Open email <ChevronRight size={14} />
            </Link>
          </div>
        </aside>
      </div>
    </>
  );
}
