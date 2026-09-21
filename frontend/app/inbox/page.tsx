"use client";

import Link from "next/link";
import {TrashControls} from "@/components/inbox/trash-controls";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { api, post, uploadDocument, waitForJob } from "@/lib/api/client";
import type { InboxCounts, InboxItem, InboxPage } from "@/lib/api/types";
import { filtersFromUrl, listQuery, PROCESSABLE_ACTIONS, urlFor, type InboxFilters } from "@/lib/inbox";
import { Button } from "@/components/ui/button";
import { SampleFetch } from "@/components/sample-fetch";
import { useAuth } from "@/components/auth-provider";
import { EmailPreview, type PreviewEmail } from "@/components/inbox/email-preview";
import { EmailRow } from "@/components/inbox/email-row";
import { FilterBar } from "@/components/inbox/filter-bar";

const PAGE = 25;
const MAX_RELOAD = 100;
const POLL_MS = 8000;

const isAbort = (error: unknown) => (error as Error)?.name === "AbortError";

/** The freshest view of the previewed email: the full record wins over the list row it came from. */
function withDetail(base: InboxItem, detail: PreviewEmail | null): InboxItem {
  if (!detail || detail.id !== base.id || !detail.state || !detail.tone) return base;
  return {
    ...base,
    state: detail.state,
    state_label: detail.state_label ?? base.state_label,
    tone: detail.tone,
    reasons: detail.reasons ?? base.reasons,
    action: detail.action ?? base.action,
    documents: detail.documents ?? base.documents,
    case: detail.case === undefined ? base.case : detail.case,
  };
}

export default function Inbox() {
  const router = useRouter();
  const auth = useAuth();
  const canAct = auth.role !== "viewer";

  const [items, setItems] = useState<InboxItem[]>([]);
  const [total, setTotal] = useState(0);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [counts, setCounts] = useState<InboxCounts | null>(null);
  const [filters, setFilters] = useState<InboxFilters>({ state: "all", category: "all", q: "" });
  const [searchText, setSearchText] = useState("");
  const [ready, setReady] = useState(false); // filters from the URL are applied before the first fetch
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState("");
  const [reload, setReload] = useState(0);

  const [selected, setSelected] = useState<InboxItem | null>(null);
  const [detail, setDetail] = useState<PreviewEmail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState("");
  const [previewNotice, setPreviewNotice] = useState("");

  const [selecting, setSelecting] = useState(false);
  const [checked, setChecked] = useState<Set<string>>(new Set());
  const [bulkNotice, setBulkNotice] = useState("");
  const [working, setWorking] = useState(false);

  const [adding, setAdding] = useState(false);
  const [busy, setBusy] = useState("");

  // What the effects need to know without re-running when it changes.
  const generation = useRef(0); // bumped for every fresh list, so a late "load more" can be dropped
  const loaded = useRef(0);
  const keepSize = useRef(false); // a reload keeps as many rows on screen as were loaded
  const quiet = useRef(false); // a background refresh does not dim the list
  const previewRef = useRef<HTMLDivElement>(null);

  const reloadList = useCallback((options: { quiet?: boolean } = {}) => {
    keepSize.current = true;
    quiet.current = Boolean(options.quiet);
    setReload((value) => value + 1);
  }, []);

  /**
   * A real filter change starts a fresh list and closes the preview, so it never shows a stale
   * email. Re-applying the same filters (the search box does so on load) must change nothing.
   */
  const applied = useRef(filters);
  const applyFilters = useCallback((change: Partial<InboxFilters>) => {
    const next = { ...applied.current, ...change };
    if (next.state === applied.current.state && next.category === applied.current.category && next.q === applied.current.q)
      return;
    applied.current = next;
    setFilters(next);
    history.replaceState(null, "", urlFor(next));
    setSelected(null);
    setDetail(null);
    setChecked(new Set());
  }, []);

  useEffect(() => {
    const fromUrl = filtersFromUrl(new URLSearchParams(location.search));
    applied.current = fromUrl;
    setFilters(fromUrl);
    setSearchText(fromUrl.q);
    setReady(true);
  }, []);

  useEffect(() => {
    if (!ready) return;
    const timer = setTimeout(() => applyFilters({ q: searchText.trim() }), 300);
    return () => clearTimeout(timer);
  }, [searchText, applyFilters, ready]);

  // The list. Filters and search are answered by the server, so totals and paging stay correct.
  useEffect(() => {
    if (!ready) return;
    const controller = new AbortController();
    const ticket = ++generation.current;
    const limit = keepSize.current ? Math.min(MAX_RELOAD, Math.max(PAGE, loaded.current)) : PAGE;
    keepSize.current = false;
    if (!quiet.current) setLoading(true);
    quiet.current = false;
    const query = listQuery(filters);
    query.set("limit", String(limit));
    api<InboxPage>(`/emails?${query}`, { signal: controller.signal })
      .then((page) => {
        setItems(page.items);
        setTotal(page.total);
        setNextCursor(page.next_cursor);
        loaded.current = page.items.length;
        setError("");
        setSelected((current) => (current ? (page.items.find((item) => item.id === current.id) ?? current) : current));
      })
      .catch((failure) => {
        if (!isAbort(failure)) setError((failure as Error).message);
      })
      .finally(() => {
        if (generation.current === ticket) setLoading(false);
      });
    return () => controller.abort();
  }, [filters, reload, ready]);

  // Filter badges. They describe the whole mailbox, so a failure here must not hide the list.
  useEffect(() => {
    const controller = new AbortController();
    api<InboxCounts>("/emails/counts", { signal: controller.signal })
      .then(setCounts)
      .catch(() => undefined);
    return () => controller.abort();
  }, [reload]);

  // The full record of the previewed email, refetched whenever the list is.
  const selectedId = selected?.id ?? null;
  useEffect(() => {
    if (!selectedId) return;
    const controller = new AbortController();
    setDetailLoading(true);
    setDetailError("");
    api<PreviewEmail>(`/emails/${selectedId}`, { signal: controller.signal })
      .then(setDetail)
      .catch((failure) => {
        if (!isAbort(failure)) setDetailError(`Could not load the full email: ${(failure as Error).message}`);
      })
      .finally(() => {
        if (!controller.signal.aborted) setDetailLoading(false);
      });
    return () => controller.abort();
  }, [selectedId, reload]);

  // While anything in the mailbox is being read, check back until it settles. The mailbox-wide
  // count is what matters: a filter can hide every row that is still processing.
  const anyProcessing =
    (counts?.by_state.processing ?? 0) > 0 ||
    items.some((item) => item.state === "processing") ||
    selected?.state === "processing";
  useEffect(() => {
    if (!anyProcessing) return;
    const refresh = () => {
      if (!document.hidden) reloadList({ quiet: true });
    };
    const timer = setInterval(refresh, POLL_MS);
    document.addEventListener("visibilitychange", refresh); // catch up as soon as the tab is back
    return () => {
      clearInterval(timer);
      document.removeEventListener("visibilitychange", refresh);
    };
  }, [anyProcessing, reloadList]);

  useEffect(()=>{const changed=()=>{setSelected(null);setDetail(null);setChecked(new Set());reloadList()};window.addEventListener("draftwise:inbox-changed",changed);return()=>window.removeEventListener("draftwise:inbox-changed",changed)},[reloadList]);

  async function loadMore() {
    if (!nextCursor) return;
    const ticket = generation.current;
    setLoadingMore(true);
    const query = listQuery(filters);
    query.set("limit", String(PAGE));
    query.set("offset", nextCursor);
    try {
      const page = await api<InboxPage>(`/emails?${query}`);
      if (generation.current !== ticket) return; // the filters changed while this was loading
      setItems((current) => [...current, ...page.items.filter((item) => !current.some((known) => known.id === item.id))]);
      loaded.current += page.items.length;
      setTotal(page.total);
      setNextCursor(page.next_cursor);
    } catch (failure) {
      setError((failure as Error).message);
    } finally {
      setLoadingMore(false);
    }
  }

  function select(item: InboxItem) {
    if (item.id === selected?.id) return;
    setSelected(item);
    setDetail(null);
    setDetailError("");
    setPreviewNotice("");
    if (window.matchMedia("(max-width: 1023px)").matches) {
      requestAnimationFrame(() => previewRef.current?.scrollIntoView({ block: "start" }));
    }
  }

  function closePreview() {
    setSelected(null);
    setDetail(null);
  }

  /** Read and compare with local rules only. Nothing here spends AI. */
  async function processEmails(targets: InboxItem[], onDone: (message: string) => void) {
    setWorking(true);
    let queued = 0;
    let failed = 0;
    for (const target of targets) {
      try {
        await post(`/emails/${target.id}/process`, { prefer_ai: false });
        queued += 1;
      } catch {
        failed += 1;
      }
    }
    onDone(
      `${queued} email${queued === 1 ? "" : "s"} queued without AI${failed ? `; ${failed} could not be queued` : ""}. The state updates when reading finishes.`,
    );
    setWorking(false);
    reloadList();
  }

  const toggleChecked = (id: string, on: boolean) =>
    setChecked((current) => {
      const next = new Set(current);
      if (on) next.add(id);
      else next.delete(id);
      return next;
    });
  const picked = items.filter((item) => checked.has(item.id));
  const pickedEligible = picked.filter((item) => PROCESSABLE_ACTIONS.has(item.action.kind));

  function toggleSelecting() {
    setSelecting((on) => !on);
    setChecked(new Set());
    setBulkNotice("");
  }

  async function add(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    const form = new FormData(event.currentTarget);
    let savedId: string | null = null;
    try {
      setBusy("Saving the email…");
      const email = await post<{ id: string }>("/emails", {
        external_id: crypto.randomUUID(),
        source_namespace: "manual",
        from: form.get("sender"),
        subject: form.get("subject"),
        body: form.get("body"),
      });
      savedId = email.id;
      const files = form
        .getAll("documents")
        .filter((value): value is File => value instanceof File && value.size > 0);
      if (files.length > 20) throw new Error("Add no more than 20 documents to one email.");
      const attachments: string[] = [];
      for (const file of files) {
        setBusy(`Uploading ${file.name}…`);
        attachments.push(await uploadDocument(email.id, file));
      }
      setBusy("Identifying the requested action…");
      const classification = await post<{ job_id: string }>("/classify", { email_id: email.id });
      await waitForJob(classification.job_id);
      if (attachments.length) {
        setBusy("Reading document evidence…");
        const extraction = await post<{ job_id: string }>("/extract", { attachment_ids: attachments });
        await waitForJob(extraction.job_id);
      }
      const reference = String(form.get("reference") || "").trim();
      if (reference) {
        const result = await post<{ id: string }>("/cases", { email_id: email.id, reference });
        router.push(`/cases/${result.id}`);
      } else router.push(`/inbox/${email.id}`);
    } catch (failure) {
      setError(
        `${(failure as Error).message}${savedId ? " The email is saved and now appears in the list below." : ""}`,
      );
      if (savedId) reloadList();
    } finally {
      setBusy("");
    }
  }

  const filtered = filters.state !== "all" || filters.category !== "all" || filters.q !== "";
  const previewItem = selected ? withDetail(selected, detail?.id === selected.id ? detail : null) : null;

  return (
    <>
      <Link href="/trash" className="inline-block mb-3 underline">Trash and restore</Link>
      {canAct && checked.size>0 && <TrashControls ids={[...checked]}/>} 
      <header className="flex items-start justify-between gap-4">
        <div>
          <h1 className="mt-2 text-3xl font-semibold">Inbox</h1>
          <p className="mt-3 text-slate-600">
            Every email, what it needs next and why. Open one to see its documents and extracted values.
          </p>
        </div>
        <Button disabled={!canAct || Boolean(busy)} onClick={() => setAdding(!adding)}>
          {adding ? "Close form" : "Add email"}
        </Button>
      </header>
      <SampleFetch />
      {error && (
        <p role="alert" className="mt-5 rounded-lg bg-red-50 p-4 text-sm text-red-800">
          {error}
        </p>
      )}
      {adding && (
        <form onSubmit={add} className="card mt-6 grid gap-4 p-6 sm:grid-cols-2">
          <h2 className="font-semibold sm:col-span-2">Add a shipment request</h2>
          <label className="text-sm font-medium">
            Sender email
            <input className="input mt-1" name="sender" type="email" required />
          </label>
          <label className="text-sm font-medium">
            Shipment reference
            <input className="input mt-1" name="reference" required maxLength={120} placeholder="Booking or shipment reference" />
          </label>
          <label className="text-sm font-medium sm:col-span-2">
            Subject
            <input className="input mt-1" name="subject" required maxLength={1000} />
          </label>
          <label className="text-sm font-medium sm:col-span-2">
            Original email body
            <textarea className="input mt-1 min-h-40" name="body" required maxLength={100000} />
          </label>
          <label className="text-sm font-medium sm:col-span-2">
            Shipping instructions and draft BL
            <input className="input mt-1" name="documents" type="file" accept=".txt,.pdf,.docx,.xlsx" multiple />
            <span className="mt-1 block text-xs font-normal text-slate-500">PDF, Word, Excel or text · up to 20 MB each</span>
          </label>
          <div className="sm:col-span-2">
            <Button disabled={Boolean(busy)}>{busy || "Save and prepare case"}</Button>
            <p role="status" className="mt-2 text-sm text-brand-900">
              {busy}
            </p>
          </div>
        </form>
      )}

      <FilterBar filters={filters} counts={counts} searchText={searchText} onSearch={setSearchText} onChange={applyFilters} />

      <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
        <p role="status" className="text-sm text-slate-700">
          {loading && !items.length
            ? "Loading inbox…"
            : `Showing ${items.length} of ${total} email${total === 1 ? "" : "s"}${filtered ? " matching your filters" : ""}`}
        </p>
        <div className="flex flex-wrap items-center gap-2">
          {selecting && (
            <>
              <label className="flex items-center gap-1.5 text-xs font-medium text-slate-700">
                <input
                  type="checkbox"
                  className="size-4 accent-brand-800"
                  checked={items.length > 0 && picked.length === items.length}
                  onChange={(event) => setChecked(event.target.checked ? new Set(items.map((item) => item.id)) : new Set())}
                />
                Select all shown
              </label>
              <Button
                disabled={!canAct || working || !pickedEligible.length}
                onClick={() => void processEmails(pickedEligible, setBulkNotice)}
              >
                {working ? "Working…" : `Read without AI (${pickedEligible.length})`}
              </Button>
            </>
          )}
          <Button variant="outline" onClick={toggleSelecting}>
            {selecting ? "Done selecting" : "Select emails"}
          </Button>
        </div>
      </div>
      {selecting && (
        <p role="status" className="mt-2 text-xs text-slate-600">
          {bulkNotice ||
            `${picked.length} selected${picked.length > pickedEligible.length ? `; ${picked.length - pickedEligible.length} cannot be read or compared` : ""}.`}
        </p>
      )}

      <div className="mt-4 grid grid-cols-1 gap-6 lg:grid-cols-12">
        <section
          className={`card overflow-hidden ${previewItem ? "lg:col-span-5" : "lg:col-span-12"}`}
          aria-label="Emails"
          aria-busy={loading}
        >
          {loading && !items.length ? (
            <p className="p-6 text-sm text-slate-600">Loading inbox…</p>
          ) : !items.length ? (
            <div className="px-6 py-16 text-center">
              <h2 className="font-semibold text-slate-900">{filtered ? "No emails match these filters" : "No emails yet"}</h2>
              <p className="mt-2 text-sm text-slate-600">
                {filtered ? "Clear a filter or change the search." : "Add an email above to get started."}
              </p>
            </div>
          ) : (
            <ul className={`divide-y divide-slate-200 transition-opacity ${loading ? "opacity-60" : ""}`}>
              {items.map((item) => (
                <EmailRow
                  key={item.id}
                  item={item}
                  selected={item.id === selected?.id}
                  selecting={selecting}
                  checked={checked.has(item.id)}
                  onSelect={() => select(item)}
                  onCheck={(on) => toggleChecked(item.id, on)}
                />
              ))}
            </ul>
          )}
        </section>

        {previewItem && (
          <div ref={previewRef} className="lg:col-span-7 lg:self-start">
            <div className="lg:sticky lg:top-4 lg:max-h-[calc(100vh-2rem)] lg:overflow-y-auto">
              <EmailPreview
                item={previewItem}
                detail={detail?.id === previewItem.id ? detail : null}
                loading={detailLoading}
                error={detailError}
                canAct={canAct}
                busy={working}
                notice={previewNotice}
                onClose={closePreview}
                onProcess={() => void processEmails([previewItem], setPreviewNotice)}
              />
            </div>
          </div>
        )}
      </div>

      {nextCursor && (
        <Button className="mt-4" variant="outline" onClick={loadMore} disabled={loadingMore}>
          {loadingMore ? "Loading…" : `Load more emails (${Math.max(total - items.length, 0)} left)`}
        </Button>
      )}
    </>
  );
}
