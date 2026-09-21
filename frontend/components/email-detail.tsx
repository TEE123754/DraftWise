"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { api, post, uploadDocument } from "@/lib/api/client";
import type { Email } from "@/lib/api/types";
import { AiUsage } from "@/components/ai-usage";
import { EmailWorkflow, type WorkflowEmail } from "@/components/email-workflow";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/components/auth-provider";

export function EmailDetail({ emailId }: { emailId: string }) {
  const auth = useAuth();
  const [email, setEmail] = useState<(Email & WorkflowEmail) | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState("");
  const [caseId, setCaseId] = useState<string | null>(null);
  const load = useCallback(async () => {
    try {
      setEmail(await api<Email & WorkflowEmail>(`/emails/${emailId}`));
    } catch (error) {
      setError((error as Error).message);
    }
  }, [emailId]);
  useEffect(() => {
    void load();
  }, [load]);
  useEffect(() => {
    if (!email?.workflow || !["queued","running","retry_wait"].includes(email.workflow.job_state || "")) return;
    const timer=setInterval(()=>void load(),2500);
    return ()=>clearInterval(timer);
  },[email?.workflow?.job_state,load]);
  async function addFile(file: File) {
    setBusy("Uploading document…");
    setError("");
    try {
      await uploadDocument(emailId, file);
      await load();
    } catch (error) {
      setError((error as Error).message);
    } finally {
      setBusy("");
    }
  }
  async function createCase(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy("Opening case…");
    try {
      const result = await post<{ id: string }>("/cases", {
        email_id: emailId,
        reference: new FormData(event.currentTarget).get("reference"),
      });
      setCaseId(result.id);
    } catch (error) {
      setError((error as Error).message);
    } finally {
      setBusy("");
    }
  }
  return (
    <>
      <Link href="/inbox" className="text-sm text-brand-800">
        ← Inbox
      </Link>
      {error && (
        <p role="alert" className="mt-4 text-red-800">
          {error}
        </p>
      )}
      {email ? (
        <>
          {email.display_id && <p className="mt-5 font-mono text-sm font-semibold text-slate-600">{email.display_id}</p>}
          <h1 className="mt-1 text-3xl font-semibold">{email.subject}</h1>
          <p className="mt-2 text-sm text-slate-500">From {email.sender}</p>
          <AiUsage className="mt-1 text-xs text-slate-700" />
          <article className="card mt-6 whitespace-pre-wrap p-6 text-sm leading-7">
            {email.body}
          </article>
          <EmailWorkflow emailId={emailId} email={email} onReload={load}/>
          {email.body_extraction && (
            <section className="card mt-6 p-5" aria-labelledby="email-fields-title">
              <h2 id="email-fields-title" className="font-semibold">Information found in this email</h2>
              <p className="mt-2 text-sm text-slate-600">
                Labelled fields from the current message. These values are not confirmed shipping instructions.
                {email.body_extraction.quoted_history_excluded && " Quoted history was excluded."}
                {" "}Unlabelled prose may require manual review.
              </p>
              <dl className="mt-4 divide-y divide-slate-200">
                {Object.entries(email.body_extraction.extraction.fields).map(([name, field]) => (
                  <div key={name} className="py-3">
                    <dt className="text-sm font-semibold capitalize">{name.replaceAll("_", " ")}</dt>
                    <dd className="mt-1 text-sm">
                      {field.state === "present" ? field.raw_value : field.state === "ambiguous"
                        ? `Conflicting values: ${field.alternatives.join("; ")}` : "Not found in labelled email text"}
                      {field.evidence.length > 0 && (
                        <details className="mt-2 text-slate-600">
                          <summary className="cursor-pointer">Source evidence</summary>
                          {field.evidence.map((item) => <blockquote key={item.block_id} className="mt-2 whitespace-pre-wrap">{item.quote}</blockquote>)}
                        </details>
                      )}
                    </dd>
                  </div>
                ))}
              </dl>
            </section>
          )}
          <section className="card mt-6 p-5">
            <h2 className="font-semibold">Documents</h2>
            <ul className="mt-3 space-y-2">
              {email.attachments?.map((attachment) => (
                <li
                  key={attachment.id}
                  className="flex justify-between gap-4 text-sm"
                >
                  <span>{attachment.original_name}</span>
                  <span className="text-slate-500">{attachment.state}</span>
                </li>
              ))}
            </ul>
            <label className="mt-5 block text-sm font-medium">
              Add a document
              <input
                className="input mt-2"
                type="file"
                accept=".txt,.pdf,.docx,.xlsx"
                disabled={Boolean(busy) || auth.role === "viewer"}
                onChange={(e) => {
                  const file = e.target.files?.[0];
                  if (file) void addFile(file);
                }}
              />
            </label>
            <p role="status" className="mt-2 text-sm">
              {busy}
            </p>
          </section>
          <form onSubmit={createCase} className="card mt-6 p-5">
            <label htmlFor="shipment-reference" className="text-sm font-medium">
              Shipment reference
            </label>
            <input
              id="shipment-reference"
              className="input mt-2"
              name="reference"
              required
              maxLength={120}
            />
            <Button
              className="mt-3"
              disabled={Boolean(busy) || auth.role === "viewer"}
            >
              Open amendment case
            </Button>
            {caseId && (
              <Link
                href={`/cases/${caseId}`}
                className="ml-4 text-sm font-semibold text-brand-800 underline"
              >
                Continue to case →
              </Link>
            )}
          </form>
        </>
      ) : (
        <p role="status" className="mt-6">
          Loading email…
        </p>
      )}
    </>
  );
}
