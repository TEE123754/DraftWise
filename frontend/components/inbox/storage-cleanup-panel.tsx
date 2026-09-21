"use client";
import { useCallback, useEffect, useState } from "react";
import { api, post } from "@/lib/api/client";
import { Button } from "@/components/ui/button";

type Item = {
  id: string;
  storage_key: string;
  file_name: string;
  state: "pending" | "failed";
  attempts: number;
  last_error: string | null;
  next_attempt_at: string | null;
  created_at: string;
};
type Listing = {
  by_state: Record<"pending" | "deleted" | "skipped" | "failed", number>;
  storage_configured: boolean;
  items: Item[];
};

/**
 * Administrators only. Uploaded files are deleted by the worker after their email leaves Trash; this
 * lists the ones storage refused, so they are never silently kept, and lets an administrator retry.
 */
export function StorageCleanupPanel() {
  const [data, setData] = useState<Listing | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState<string | null>(null);
  const [notice, setNotice] = useState("");

  const load = useCallback(() => {
    api<Listing>("/storage-cleanup")
      .then((listing) => {
        setData(listing);
        setError("");
      })
      .catch((failure) => setError((failure as Error).message));
  }, []);
  useEffect(load, [load]);

  async function retry(item: Item) {
    setBusy(item.id);
    setNotice("");
    try {
      await post(`/storage-cleanup/${item.id}/retry`, {});
      setNotice(`${item.file_name} is queued again. The worker retries it on its next pass.`);
      load();
    } catch (failure) {
      setError((failure as Error).message);
    } finally {
      setBusy(null);
    }
  }

  return (
    <section className="card mt-8 p-5" aria-labelledby="storage-cleanup-title">
      <h2 id="storage-cleanup-title" className="font-semibold">
        File deletion after Trash
      </h2>
      <p className="mt-1 text-sm text-slate-600">
        When an email is purged from Trash, its uploaded files are deleted from storage. Files that storage would
        not delete are listed here.
      </p>
      {error && (
        <p role="alert" className="mt-3 text-sm text-red-800">
          {error}
        </p>
      )}
      {notice && (
        <p role="status" className="mt-3 text-sm text-green-800">
          {notice}
        </p>
      )}
      {data && (
        <>
          <dl className="mt-4 grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
            {(
              [
                ["Waiting", data.by_state.pending],
                ["Deleted", data.by_state.deleted],
                ["Kept (still linked)", data.by_state.skipped],
                ["Failed", data.by_state.failed],
              ] as const
            ).map(([label, value]) => (
              <div key={label} className="rounded-md border border-slate-200 p-3">
                <dt className="text-xs text-slate-600">{label}</dt>
                <dd className="text-lg font-semibold" data-cleanup-count={label}>
                  {value}
                </dd>
              </div>
            ))}
          </dl>
          {!data.storage_configured && (
            <p className="mt-3 text-sm text-yellow-900">
              Storage is not configured, so queued files wait until it is.
            </p>
          )}
          {data.items.length === 0 ? (
            <p className="mt-4 text-sm">No file has failed to delete.</p>
          ) : (
            <ul className="mt-4 divide-y divide-slate-200">
              {data.items.map((item) => (
                <li key={item.id} className="flex flex-col gap-2 py-3 sm:flex-row sm:items-center sm:justify-between">
                  <div className="min-w-0">
                    <p className="truncate font-medium" title={item.storage_key}>
                      {item.file_name}
                    </p>
                    <p className="text-xs text-slate-600">
                      {item.state === "failed" ? "Gave up" : "Retrying"} after {item.attempts} attempt
                      {item.attempts === 1 ? "" : "s"}
                      {item.last_error ? ` (${item.last_error})` : ""}
                      {item.state === "pending" && item.next_attempt_at
                        ? `; next try ${new Date(item.next_attempt_at).toLocaleString()}`
                        : ""}
                    </p>
                  </div>
                  {item.state === "failed" && (
                    <Button
                      variant="secondary"
                      size="sm"
                      disabled={busy !== null}
                      onClick={() => void retry(item)}
                      tip={{ name: "Retry deletion", description: "Queues this file for deletion again with a fresh set of attempts" }}
                    >
                      {busy === item.id ? "Queuing…" : "Retry deletion"}
                    </Button>
                  )}
                </li>
              ))}
            </ul>
          )}
        </>
      )}
    </section>
  );
}
