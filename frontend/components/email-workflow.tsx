"use client";
import Link from "next/link";
import { useState } from "react";
import { post } from "@/lib/api/client";
import { useAuth } from "@/components/auth-provider";
import { Button } from "@/components/ui/button";
import { DocumentActions } from "@/components/document-actions";
import { TrashControls } from "@/components/inbox/trash-controls";

type Run = {
  method?: string;
  provider?: string;
  fallback_reason?: string;
  reason_code?: string;
  evidence?: { id: string; text: string }[];
  senses?: {
    term?: string;
    sense?: string | null;
    state: string;
    quote?: string;
  }[];
};
export type WorkflowEmail = {
  state?: string;
  documents?: { si: boolean; bl: boolean; unread: number };
  case?: { id: string } | null;
  classification?: {
    category: string;
    ambiguous: boolean;
    run_metadata: Run;
  } | null;
  safety?: {
    risk_state: string;
    held_for_review: boolean;
    signals: { description: string; evidence: string }[];
    release_reason?: string;
  } | null;
  workflow?: {
    state: string;
    case_id?: string;
    job_state?: string;
    error_code?: string;
    details: { next_action?: string };
  } | null;
  extractions?: {
    id: string;
    attachment_id: string;
    document_type: string;
    output: {
      fields: Record<
        string,
        {
          state: string;
          raw_value: string | null;
          alternatives: string[];
          evidence: { block_id: string; quote: string }[];
        }
      >;
    };
    run_metadata: Run;
  }[];
};
export function EmailWorkflow({
  emailId,
  email,
  onReload,
}: {
  emailId: string;
  email: WorkflowEmail;
  onReload: () => Promise<void>;
}) {
  const auth = useAuth();
  const [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  const [reason, setReason] = useState(""),
    [category, setCategory] = useState("GENERAL");
  const working = ["queued", "running", "retry_wait"].includes(
    email.workflow?.job_state || "",
  );
  const held = email.safety?.held_for_review;
  const reviewer = ["admin", "reviewer"].includes(auth.role);
  const caseId = email.case?.id || email.workflow?.case_id;
  async function act(path: string, body: unknown) {
    setBusy(true);
    setError("");
    try {
      await post(path, body);
      await onReload();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  const steps = [
    ["Intake", "Email received. Attachments remain linked to this request."],
    [
      "Classify",
      email.classification?.ambiguous
        ? "Intent needs review"
        : email.classification?.category.replaceAll("_", " ") ||
          "Not classified",
    ],
    [
      "Documents",
      email.documents
        ? `SI: ${email.documents.si ? "found" : "missing"}. BL: ${email.documents.bl ? "found" : "missing"}.`
        : "Inspect attached document types below.",
    ],
    [
      "Extract",
      working
        ? "Processing documents"
        : email.extractions?.length
          ? `${email.extractions.length} documents read; inspect missing or uncertain fields below.`
          : "No document extraction yet.",
    ],
    [
      "Compare",
      email.classification &&
      !email.classification.ambiguous &&
      email.classification.category !== "BL_COMPARISON"
        ? "Not required for this email category"
        : email.state === "checked"
          ? "All seven required fields match"
          : email.state === "mismatch_found"
            ? "Differences require review"
            : "Comparison is incomplete or needs review.",
    ],
    [
      "Decide / Reply",
      held
        ? "Review the safety hold before processing."
        : email.workflow?.details.next_action ||
          "Inspect evidence, request missing documents, or prepare a reply.",
    ],
  ];
  return (
    <section className="card mt-6 p-5" aria-label="Email review workflow">
      <h2 className="font-semibold">Email review workflow</h2>
      <ol className="mt-4 space-y-3">
        {steps.map(([title, description], i) => (
          <li key={title} className="rounded border border-slate-200 p-3">
            <h3 className="font-semibold">
              {i + 1}. {title}
            </h3>
            <p className="text-sm mt-1">{description}</p>
          </li>
        ))}
      </ol>
      {error && (
        <p role="alert" className="mt-3">
          {error}
        </p>
      )}
      <div className="flex flex-wrap gap-3 mt-4">
        <Button
          disabled={busy || working || held || auth.role === "viewer"}
          onClick={() =>
            void act(`/emails/${emailId}/process`, { prefer_ai: false })
          }
        >
          Review with local rules
        </Button>
        <Button
          variant="outline"
          disabled={busy || working || held || auth.role === "viewer"}
          onClick={() =>
            void act(`/emails/${emailId}/process`, { prefer_ai: true })
          }
        >
          Review with AI
        </Button>
        {caseId && (
          <Link className="underline self-center" href={`/cases/${caseId}`}>
            Open document comparison
          </Link>
        )}
      </div>
      {email.classification && (
        <details className="mt-4">
          <summary>Classification evidence and word meanings</summary>
          <p>
            Method:{" "}
            {email.classification.run_metadata.method ||
              email.classification.run_metadata.provider ||
              "rules"}
          </p>
          {email.classification.run_metadata.fallback_reason && (
            <p>Fallback: {email.classification.run_metadata.fallback_reason}</p>
          )}
          {email.classification.run_metadata.evidence?.map((e) => (
            <blockquote key={e.id} className="whitespace-pre-wrap text-sm mt-2">
              {e.text}
            </blockquote>
          ))}
          {email.classification.run_metadata.senses?.map((s, i) => (
            <p key={i}>
              {s.term}: {s.sense || "Needs review"} {s.quote}
            </p>
          ))}
        </details>
      )}
      {email.safety && (
        <section className="mt-5" aria-label="Email safety">
          <h3 className="font-semibold">Spam and phishing signals</h3>
          <p className="text-sm">
            {held
              ? "Processing held for a reviewer."
              : "Static signals are not a guarantee of safety."}{" "}
            No sanctions or restricted-goods screening is performed.
          </p>
          {email.safety.signals.map((s, i) => (
            <blockquote key={i} className="text-sm mt-2">
              {s.description}: {s.evidence}
            </blockquote>
          ))}
          {held && reviewer && (
            <>
              <label className="block text-sm mt-3">
                Release reason
                <textarea
                  className="input"
                  value={reason}
                  onChange={(e) => setReason(e.target.value)}
                />
              </label>
              <Button
                disabled={busy || reason.trim().length < 5}
                onClick={() =>
                  void act(`/emails/${emailId}/release`, { reason })
                }
              >
                Release for processing
              </Button>
            </>
          )}
        </section>
      )}
      <DocumentActions
        emailId={emailId}
        onChanged={onReload}
        refreshKey={`${email.state}-${email.workflow?.job_state}-${email.extractions?.map((x) => x.id).join()}`}
      />
      {email.extractions?.map((x) => (
        <details key={x.id} className="mt-4">
          <summary>{x.document_type} extracted fields</summary>
          <p className="text-sm">
            Method: {x.run_metadata.method || x.run_metadata.provider}
            {x.run_metadata.fallback_reason &&
              ` (${x.run_metadata.fallback_reason})`}
          </p>
          <dl>
            {Object.entries(x.output.fields).map(([name, f]) => (
              <div key={name} className="py-2">
                <dt className="font-semibold">{name.replaceAll("_", " ")}</dt>
                <dd>
                  {f.raw_value || f.state}
                  {f.evidence.map((e, i) => (
                    <blockquote className="text-sm whitespace-pre-wrap" key={i}>
                      {e.quote}
                    </blockquote>
                  ))}
                </dd>
              </div>
            ))}
          </dl>
        </details>
      ))}
      {reviewer && (
        <details className="mt-4">
          <summary>Review the email category</summary>
          <label className="block">
            Category
            <select
              className="input"
              value={category}
              onChange={(e) => setCategory(e.target.value)}
            >
              {[
                "BL_COMPARISON",
                "SI_REQUEST",
                "INVOICE_QUERY",
                "GENERAL",
                "SPAM",
              ].map((c) => (
                <option key={c}>{c}</option>
              ))}
            </select>
          </label>
          <label className="block mt-2">
            Review reason
            <textarea
              className="input"
              value={reason}
              onChange={(e) => setReason(e.target.value)}
            />
          </label>
          <Button
            disabled={busy || working || reason.trim().length < 5}
            onClick={() =>
              void act(`/emails/${emailId}/classification-review`, {
                category,
                reason,
              })
            }
          >
            Save reviewed category
          </Button>
        </details>
      )}
      {auth.role !== "viewer" && <TrashControls ids={[emailId]} />}
    </section>
  );
}
