"use client";
import { useState } from "react";
import Link from "next/link";
import { useAuth } from "@/components/auth-provider";
import { post } from "@/lib/api/client";
import { Button } from "@/components/ui/button";

type FetchResult = { fetched: number; imported: number; reused: number; queued_for_reading: number; message: string };

/** Demo only: simulates the first Gmail fetch by pulling in the whole supplied sample mailbox. */
export function SampleFetch() {
  const auth = useAuth();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<FetchResult | null>(null);
  if (!auth.demo) return null;
  async function fetchMailbox() {
    setBusy(true);
    setError("");
    try {
      setResult(await post<FetchResult>("/demo/gmail/fetch", { prefer_ai: false }));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="card mt-6 p-5" aria-labelledby="sample-fetch-title">
      <h2 id="sample-fetch-title" className="font-semibold">Fetch the sample mailbox</h2>
      <p className="mt-2 text-sm text-slate-600">
        A simulation of a first Gmail fetch: no Google account is connected. It fetches the supplied sample
        mailbox of 520 emails. Emails already in your workspace are reused, never duplicated, and the
        comparison emails are read with rules only. Ask for AI from an email page if you want it.
      </p>
      <div className="mt-4 flex flex-wrap items-center gap-3">
        <Button
          onClick={fetchMailbox}
          disabled={busy}
          tip={{ name: "Simulate Gmail fetch", description: "Fetches the 520 sample emails; no Google account is used" }}
        >
          {busy ? "Fetching 520 emails…" : "Simulate Gmail fetch"}
        </Button>
        {result && (
          <Link href="/inbox" className="text-sm font-semibold underline">
            Open the inbox
          </Link>
        )}
      </div>
      {result && (
        <p role="status" className="mt-3 text-sm text-slate-800">
          {result.message}
          {result.queued_for_reading > 0 && ` Reading of ${result.queued_for_reading} comparison emails has been queued.`}
        </p>
      )}
      {error && (
        <p role="alert" className="mt-3 text-red-800">
          {error}
        </p>
      )}
    </section>
  );
}
