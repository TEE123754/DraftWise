"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api } from "@/lib/api/client";
import type { CaseSummary, Readiness } from "@/lib/api/types";
import { Button } from "@/components/ui/button";
import { StatusBadge } from "./status-badge";

export function CaseQueue({
  completed = false,
  initialFilter = "",
  initialSearch = "",
  openOnly = false,
}: {
  completed?: boolean;
  initialFilter?: Readiness | "";
  initialSearch?: string;
  openOnly?: boolean;
}) {
  const [items, setItems] = useState<CaseSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [search, setSearch] = useState(initialSearch);
  const [filter, setFilter] = useState<Readiness | "">(
    completed ? "checked" : initialFilter,
  );
  const [cursor, setCursor] = useState<string | null>(null);
  const [refresh, setRefresh] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    const timer = setTimeout(() => {
      setLoading(true);
      setError("");
      const params = new URLSearchParams({ search });
      if (openOnly && !filter) params.set("open", "true");
      if (filter) params.set("readiness", filter);
      api<{ items: CaseSummary[]; next_cursor: string | null }>(
        `/cases?${params}`,
        { signal: controller.signal },
      )
        .then((result) => {
          setItems(result.items);
          setCursor(result.next_cursor);
        })
        .catch((error) => {
          if (error.name !== "AbortError") setError(error.message);
        })
        .finally(() => {
          if (!controller.signal.aborted) setLoading(false);
        });
    }, 200);
    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [search, filter, refresh, openOnly]);
  async function loadMore() {
    setLoading(true);
    try {
      const params = new URLSearchParams({ search, cursor: cursor! });
      if (openOnly && !filter) params.set("open", "true");
      if (filter) params.set("readiness", filter);
      const result = await api<{
        items: CaseSummary[];
        next_cursor: string | null;
      }>(`/cases?${params}`);
      setItems((previous) => [...previous, ...result.items]);
      setCursor(result.next_cursor);
    } catch (error) {
      setError((error as Error).message);
    } finally {
      setLoading(false);
    }
  }
  return (
    <>
      <div className="flex flex-wrap items-start justify-between gap-5">
        <div>
          <h1 className="text-3xl font-semibold tracking-tight">
            {completed ? "Completed checks" : "Attention queue"}
          </h1>
          <p className="mt-3 text-slate-600">
            {completed
              ? "Drafts that match all seven fields in the pinned instructions."
              : "Review shipping instructions, draft differences and returned revisions."}
          </p>
        </div>
        <Button asChild>
          <Link href="/inbox">Add a shipment</Link>
        </Button>
      </div>
      <section
        className="card mt-8 overflow-hidden"
        aria-label="Shipment cases"
      >
        <div className="flex flex-wrap gap-3 border-b border-slate-200 p-4">
          <div className="relative min-w-56 flex-1">
            <input
              aria-label="Search case reference"
              className="input"
              placeholder="Find a shipment reference…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>
          {!completed && (
            <select
              aria-label="Filter by next action"
              className="input w-auto"
              value={filter}
              onChange={(e) => setFilter(e.target.value as Readiness | "")}
            >
              <option value="">All cases</option>
              <option value="needs_decision">Needs a decision</option>
              <option value="changes_required">Changes required</option>
              <option value="awaiting_revision">Awaiting revision</option>
              <option value="needs_source">Needs documents</option>
              <option value="checking">Checking</option>
              <option value="failed">Interrupted</option>
            </select>
          )}
          <Button
            variant="outline"
            aria-label="Refresh cases"
            onClick={() => setRefresh((n) => n + 1)}
          >
            Refresh
          </Button>
        </div>
        {error ? (
          <div
            role="alert"
            className="m-5 rounded-lg bg-red-50 p-4 text-sm text-red-900"
          >
            {error}
            <Button variant="ghost" onClick={() => setRefresh((n) => n + 1)}>
              Try again
            </Button>
          </div>
        ) : loading && !items.length ? (
          <p role="status" className="p-8 text-slate-500">
            Loading cases…
          </p>
        ) : !items.length ? (
          <div className="px-6 py-20 text-center">
            <h2 className="mt-4 text-lg font-semibold">
              {search || filter
                ? "No cases match this view"
                : "Your next shipment starts here"}
            </h2>
            <p className="mx-auto mt-2 max-w-md text-sm leading-6 text-slate-500">
              {completed
                ? "Completed seven-field checks will appear here."
                : "Add an email and its documents. We’ll bring the evidence and the next action into one case."}
            </p>
            {!completed && (
              <Button asChild className="mt-5">
                <Link href="/inbox">Add a shipment</Link>
              </Button>
            )}
          </div>
        ) : (
          <ul className="divide-y divide-slate-100">
            {items.map((item) => (
              <li key={item.id}>
                <Link
                  href={`/cases/${item.id}`}
                  className="group flex flex-wrap items-center justify-between gap-4 px-6 py-6 hover:bg-slate-50"
                >
                  <div className="min-w-48">
                    <div className="flex flex-wrap items-center gap-3">
                      <h2 className="font-semibold">{item.reference}</h2>
                      <StatusBadge status={item.readiness} />
                    </div>
                    <p className="mt-2 text-sm text-slate-600">
                      {item.next_action.title}
                    </p>
                  </div>
                  <div className="flex items-center gap-6 text-sm text-slate-500">
                    <span>
                      {item.open_issue_count
                        ? `${item.open_issue_count} open ${item.open_issue_count === 1 ? "issue" : "issues"}`
                        : "View case"}
                    </span>
                  </div>
                </Link>
              </li>
            ))}
          </ul>
        )}
        {cursor && (
          <div className="border-t p-4 text-center">
            <Button variant="outline" onClick={loadMore} disabled={loading}>
              Load more cases
            </Button>
          </div>
        )}
      </section>
      <p className="mt-5 text-xs text-slate-500">
        Completed checks confirm document consistency. They do not authorize
        cargo release.
      </p>
    </>
  );
}
