"use client";

import { useState } from "react";
import { Check, Copy, X } from "lucide-react";
import type { Preview } from "@/lib/api/types";
import { post } from "@/lib/api/client";
import { label } from "@/lib/utils";
import { Button } from "@/components/ui/button";

export function CorrectionPreview({
  preview,
  caseId,
  onClose,
  onShared,
}: {
  preview: Preview;
  caseId: string;
  onClose: () => void;
  onShared: () => void;
}) {
  const [requestId, setRequestId] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function copy() {
    setBusy(true);
    setError("");
    try {
      let id = requestId;
      if (!id) {
        const result = await post<{ id: string }>(`/cases/${caseId}/requests`, {
          expected_version: preview.case_version,
          preview_id: preview.id,
          message: preview.suggested_message,
        });
        id = result.id;
        setRequestId(id);
      }
      await navigator.clipboard.writeText(preview.suggested_message);
      setCopied(true);
    } catch (error) {
      setError((error as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function shared() {
    setBusy(true);
    setError("");
    try {
      await post(`/cases/${caseId}/requests/${requestId}/shared`, {
        expected_version: preview.case_version,
        note: "Reviewer confirmed the request was shared outside Draftwise.",
      });
      onShared();
    } catch (error) {
      setError((error as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <section
      className="card border-brand-200 p-6"
      aria-label="Correction preview"
    >
      <div className="flex items-start justify-between">
        <div>
          <h2 className="mt-2 text-xl font-semibold">
            {preview.remaining_blocker_count
              ? `${preview.remaining_blocker_count} fields would still need attention`
              : "Would match if these changes are applied"}
          </h2>
        </div>
        <Button
          variant="ghost"
          onClick={onClose}
          aria-label="Close correction preview"
        >
          <X size={18} />
        </Button>
      </div>
      <ul className="my-5 divide-y">
        {preview.changes.map((change) => (
          <li key={change.field} className="py-3 text-sm">
            <p className="font-medium capitalize">{label(change.field)}</p>
            <p className="mt-1 text-slate-500">
              {change.current} <span aria-label="changes to">→</span>{" "}
              <strong className="text-brand-900">{change.required}</strong>
              {change.field === "gross_weight_kg" ? " kg" : ""}
            </p>
          </li>
        ))}
      </ul>
      <label htmlFor="correction-message" className="text-sm font-semibold">
        Source-supported request
      </label>
      <textarea
        id="correction-message"
        readOnly
        className="input mt-2 min-h-48 leading-6"
        value={preview.suggested_message}
      />
      <p className="mt-3 text-xs text-slate-500">
        Copying does not send this message or fix the document. After sharing
        it, mark the request as shared.
      </p>
      {error && (
        <p role="alert" className="mt-3 text-sm text-red-800">
          {error}
        </p>
      )}
      <div className="mt-5 flex flex-wrap gap-3">
        <Button onClick={copy} disabled={busy}>
          {copied ? <Check size={16} /> : <Copy size={16} />}
          {copied ? "Copied" : "Copy correction request"}
        </Button>
        {requestId && (
          <Button variant="outline" onClick={shared} disabled={busy}>
            I’ve shared this request
          </Button>
        )}
      </div>
      <p role="status" className="mt-2 text-xs text-brand-800">
        {copied
          ? "Request copied. The current draft still has discrepancies."
          : ""}
      </p>
    </section>
  );
}
