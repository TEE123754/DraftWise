"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { api, post, uploadDocument, waitForJob } from "@/lib/api/client";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/components/auth-provider";

type Actions = {
  comparison_required?: boolean;
  missing: string[];
  kind: string;
  title: string;
  draft_reply: string;
  can_request: boolean;
  references: {
    status: string;
    email_references: { kind: string; code: string; quote: string }[];
    suggestions: {
      attachment_id: string;
      original_name: string;
      external_id: string;
      email_id: string;
      quote: string;
      code: string;
    }[];
  };
};
export function DocumentActions({
  emailId,
  onChanged,
  refreshKey,
}: {
  emailId: string;
  onChanged?: () => Promise<void>;
  refreshKey?: string | number;
}) {
  const auth = useAuth();
  const [data, setData] = useState<Actions | null>(null),
    [error, setError] = useState(""),
    [notice, setNotice] = useState(""),
    [busy, setBusy] = useState(false),
    [reason, setReason] = useState("");
  const canAct = ["operator", "reviewer", "admin"].includes(auth.role);
  useEffect(() => {
    const c = new AbortController();
    setError("");
    api<Actions>(`/emails/${emailId}/document-actions`, { signal: c.signal })
      .then((v) => {
        if (!Array.isArray(v.missing) || !v.references)
          throw new Error("Document follow-up is unavailable");
        setData(v);
      })
      .catch((e) => {
        if (!c.signal.aborted) setError(e.message);
      });
    return () => c.abort();
  }, [emailId, refreshKey]);
  async function update(task: () => Promise<unknown>) {
    setBusy(true);
    setError("");
    try {
      const result = (await task()) as { job_id?: string } | undefined;
      setNotice("Document queued for local review. No AI call was requested.");
      if (result?.job_id) await waitForJob(result.job_id);
      await onChanged?.();
      setData(await api<Actions>(`/emails/${emailId}/document-actions`));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <section
      className="card p-5 mt-4"
      aria-label="Document follow-up"
      tabIndex={-1}
    >
      <h2 className="font-semibold">Documents and next action</h2>
      {error && <p role="alert">{error}</p>}
      {!data && !error && <p role="status">Checking document availability…</p>}
      {data && (
        <>
          <p className="mt-2">
            {data.comparison_required === false
              ? "No shipping-document comparison required for this category."
              : data.missing.length
                ? `Not found: ${data.missing.join(" and ")}.`
                : "Shipping instructions and draft BL found."}
          </p>
          <p className="mt-2 text-sm">{data.title}</p>
          {data.can_request && (
            <details className="mt-3">
              <summary>Draft a reply to the sender</summary>
              <p className="text-sm mt-2">
                Local template. Review and copy it into your mail app; DraftWise
                does not send it.
              </p>
              <textarea
                aria-label="Reply draft"
                className="input mt-2"
                rows={7}
                value={data.draft_reply}
                onChange={(e) =>
                  setData({ ...data, draft_reply: e.target.value })
                }
              />
              <Button
                className="mt-2"
                onClick={async () => {
                  try {
                    await navigator.clipboard.writeText(data.draft_reply);
                    setNotice("Reply copied. Nothing was sent.");
                  } catch {
                    setError(
                      "Clipboard unavailable. Select and copy the reply text.",
                    );
                  }
                }}
              >
                Copy reply
              </Button>
            </details>
          )}
          {canAct && (
            <label className="block mt-4 text-sm">
              Upload a missing or readable document
              <input
                type="file"
                className="block mt-2"
                accept=".txt,.pdf,.docx,.xlsx"
                disabled={busy}
                onChange={(e) => {
                  const f = e.target.files?.[0];
                  if (f)
                    void update(async () => {
                      await uploadDocument(emailId, f);
                      return await post(`/emails/${emailId}/process`, {
                        prefer_ai: false,
                      });
                    });
                  e.target.value = "";
                }}
              />
            </label>
          )}
          <p className="text-sm mt-4">
            Reference check:{" "}
            {data.references.status === "matched"
              ? "An exact labelled email reference appears in its documents"
              : data.references.status === "no_reference"
                ? "No supported labelled reference found"
                : "No exact document reference found"}
            . This does not establish that all shipping fields match.
          </p>
          {data.references.suggestions.length > 0 && (
            <div className="mt-3">
              <h3 className="font-semibold">Suggested documents</h3>
              <p className="text-sm">
                Confirm the shipment before linking. Exact reference matches can
                still be reused by senders.
              </p>
              <label className="block text-sm mt-2">
                Reason for linking
                <textarea
                  className="input"
                  value={reason}
                  onChange={(e) => setReason(e.target.value)}
                  maxLength={1000}
                />
              </label>
              {data.references.suggestions.map((s, i) => (
                <div
                  className="border border-slate-200 rounded p-3 mt-2"
                  key={`${s.attachment_id}-${i}`}
                >
                  <Link href={`/inbox/${s.email_id}`}>{s.external_id}</Link>
                  <p>{s.original_name}</p>
                  <blockquote className="text-sm">{s.quote}</blockquote>
                  <Button
                    className="mt-2"
                    disabled={!canAct || busy || reason.trim().length < 5}
                    onClick={() =>
                      void update(() =>
                        post(`/emails/${emailId}/link-document`, {
                          attachment_id: s.attachment_id,
                          reason,
                        }),
                      )
                    }
                  >
                    Confirm and link document
                  </Button>
                </div>
              ))}
            </div>
          )}
        </>
      )}
      {notice && (
        <p role="status" className="mt-3 text-sm">
          {notice}
        </p>
      )}
    </section>
  );
}
