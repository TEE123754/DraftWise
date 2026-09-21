"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Mail, RefreshCw, Unlink, CheckCircle2, AlertCircle, ShieldCheck } from "lucide-react";
import { Button } from "@/components/ui/button";
import { SampleFetch } from "@/components/sample-fetch";
import { get, post, del } from "@/lib/api/client";
import type { MailboxConnectionsResponse, MailboxConnectionItem } from "@/lib/api/types";

export default function ConnectionsPage() {
  const searchParams = useSearchParams();
  const isConnected = searchParams.get("connected") === "true";
  const errorMessage = searchParams.get("error");

  const [loading, setLoading] = useState(true);
  const [data, setData] = useState<MailboxConnectionsResponse | null>(null);
  const [actionBusy, setActionBusy] = useState<string | null>(null);
  const [statusMessage, setStatusMessage] = useState<string | null>(
    isConnected
      ? "Gmail mailbox connected. It is listed below."
      : errorMessage
      ? `OAuth connection failed: ${errorMessage}`
      : null
  );

  async function loadConnections() {
    setLoading(true);
    try {
      const res = await get<MailboxConnectionsResponse>("/gmail/connections");
      setData(res);
    } catch {
      setData({
        items: [],
        available: false,
        configured: false,
        message: "Failed to load mailbox connection status.",
      });
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadConnections();
  }, []);

  async function handleConnect() {
    setActionBusy("connect");
    setStatusMessage(null);
    try {
      const res = await get<{ auth_url: string; state: string }>("/gmail/connect");
      if (res.auth_url) {
        window.location.href = res.auth_url;
      }
    } catch (err: unknown) {
      setStatusMessage(err instanceof Error ? err.message : "Failed to initiate Gmail OAuth.");
      setActionBusy(null);
    }
  }

  async function handleSync(connectionId: string) {
    setActionBusy(`sync-${connectionId}`);
    try {
      await post(`/gmail/connections/${connectionId}/sync`, {});
      setStatusMessage("Mailbox sync job enqueued. New messages will appear in Inbox shortly.");
      await loadConnections();
    } catch (err: unknown) {
      setStatusMessage(err instanceof Error ? err.message : "Sync request failed.");
    } finally {
      setActionBusy(null);
    }
  }

  async function handleDisconnect(connectionId: string) {
    if (!confirm("Are you sure you want to disconnect this Gmail mailbox? Existing imported emails will remain intact.")) {
      return;
    }
    setActionBusy(`disconnect-${connectionId}`);
    try {
      const result = await del<{ revoked: boolean; message: string | null }>(`/gmail/connections/${connectionId}`);
      setStatusMessage(result.revoked ? "Mailbox disconnected and Google access revoked." : (result.message ?? "Mailbox disconnected."));
      await loadConnections();
    } catch (err: unknown) {
      setStatusMessage(err instanceof Error ? err.message : "Disconnect request failed.");
    } finally {
      setActionBusy(null);
    }
  }

  return (
    <div className="mx-auto max-w-4xl pb-16">
      <div className="mb-6 flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900">Mailbox Connections</h1>
          <p className="mt-1 text-sm text-slate-500">
            Connect enterprise Gmail mailboxes to ingest shipping instructions and bill of lading amendments.
          </p>
        </div>
        <Link
          href="/inbox"
          className="text-xs font-semibold text-brand-800 hover:text-brand-900 underline"
        >
          Go to Inbox →
        </Link>
      </div>

      {/* Notifications / Alerts */}
      {statusMessage && (
        <div
          className={`mb-6 flex items-center gap-3 rounded-lg border p-4 text-sm font-medium ${
            statusMessage.includes("Successfully") || statusMessage.includes("enqueued")
              ? "border-emerald-200 bg-emerald-50 text-emerald-800"
              : "border-amber-200 bg-amber-50 text-amber-800"
          }`}
          role="alert"
        >
          {statusMessage.includes("Successfully") || statusMessage.includes("enqueued") ? (
            <CheckCircle2 size={18} className="shrink-0 text-emerald-600" />
          ) : (
            <AlertCircle size={18} className="shrink-0 text-amber-600" />
          )}
          <span>{statusMessage}</span>
        </div>
      )}

      {/* Connection Management Card */}
      <section className="card p-6" aria-labelledby="gmail-integration-heading">
        <div className="flex items-start justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-brand-50 text-brand-800 border border-brand-100">
              <Mail size={22} />
            </div>
            <div>
              <h2 id="gmail-integration-heading" className="text-base font-semibold text-slate-900">
                Google Workspace / Gmail Integration
              </h2>
              <p className="text-xs text-slate-500">
                Read-only scope (<code className="rounded bg-slate-100 px-1 py-0.5 font-mono text-[11px]">gmail.readonly</code>) with token isolation per workspace.
              </p>
            </div>
          </div>

          {data?.available && (
            <Button
              onClick={handleConnect}
              disabled={Boolean(actionBusy)}
              className="bg-brand-800 text-white hover:bg-brand-900 text-xs h-9 px-4"
            >
              {actionBusy === "connect" ? "Opening Google Auth…" : "Connect New Mailbox"}
            </Button>
          )}
        </div>

        {/* Status / Notice if Unavailable */}
        {loading ? (
          <div className="mt-6 py-8 text-center text-sm text-slate-500">
            Checking mailbox configuration…
          </div>
        ) : !data?.available ? (
          <div className="mt-6 rounded-lg border border-slate-200 bg-slate-50/60 p-5">
            <div className="flex items-start gap-3">
              <ShieldCheck size={20} className="mt-0.5 text-brand-700 shrink-0" />
              <div>
                <h3 className="text-sm font-semibold text-slate-800">
                  {data?.configured ? "Demo Sandbox Environment" : "Live OAuth Setup Required"}
                </h3>
                <p className="mt-1 text-xs text-slate-600 leading-relaxed">
                  {data?.message ||
                    "Secure workspace-bound OAuth is configured to protect customer email boundaries. Connect real mailboxes in full production deployment."}
                </p>
                <div className="mt-3 flex items-center gap-3">
                  <span className="inline-flex items-center rounded-full bg-slate-200 px-2.5 py-0.5 text-[11px] font-medium text-slate-700">
                    Offline Simulation Active
                  </span>
                  <Link
                    href="/workflow"
                    className="text-xs font-semibold text-brand-800 hover:text-brand-900 underline"
                  >
                    View intake workflow architecture →
                  </Link>
                </div>
              </div>
            </div>
          </div>
        ) : data.items.length === 0 ? (
          <div className="mt-6 rounded-lg border border-dashed border-slate-300 p-8 text-center">
            <Mail size={32} className="mx-auto text-slate-400" />
            <p className="mt-2 text-sm font-semibold text-slate-700">No Gmail accounts connected yet</p>
            <p className="mt-1 text-xs text-slate-500">
              Click &quot;Connect New Mailbox&quot; above to authorize DraftWise with read-only permissions.
            </p>
          </div>
        ) : (
          <div className="mt-6 divide-y divide-slate-100 rounded-lg border border-slate-200 bg-white">
            {data.items.map((conn: MailboxConnectionItem) => (
              <div key={conn.id} className="flex flex-col gap-3 p-4 sm:flex-row sm:items-center sm:justify-between">
                <div>
                  <div className="flex items-center gap-2">
                    <span className="font-semibold text-sm text-slate-900">{conn.email}</span>
                    <span
                      className={`inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-medium capitalize ${
                        conn.state === "active"
                          ? "bg-emerald-50 text-emerald-700"
                          : conn.state === "syncing"
                          ? "bg-amber-50 text-amber-700"
                          : "bg-slate-100 text-slate-600"
                      }`}
                    >
                      {conn.state}
                    </span>
                  </div>
                  <div className="mt-1 flex items-center gap-4 text-xs text-slate-500">
                    <span>Imported: <strong>{conn.messages_imported}</strong> emails</span>
                    {conn.last_sync_at && (
                      <span>Last sync: {new Date(conn.last_sync_at).toLocaleString()}</span>
                    )}
                  </div>
                  {conn.last_error && (
                    <p className="mt-1 text-xs text-red-600">Error: {conn.last_error}</p>
                  )}
                </div>

                <div className="flex items-center gap-2">
                  <Button
                    variant="outline"
                    className="h-8 px-3 text-xs"
                    onClick={() => handleSync(conn.id)}
                    disabled={Boolean(actionBusy)}
                  >
                    <RefreshCw
                      size={12}
                      className={actionBusy === `sync-${conn.id}` ? "animate-spin" : ""}
                    />
                    Sync Now
                  </Button>
                  <Button
                    variant="ghost"
                    className="h-8 px-3 text-xs text-red-600 hover:bg-red-50"
                    onClick={() => handleDisconnect(conn.id)}
                    disabled={Boolean(actionBusy)}
                  >
                    <Unlink size={12} />
                    Disconnect
                  </Button>
                </div>
              </div>
            ))}
          </div>
        )}
      </section>

      {/* Offline Sample Inbox Ingestion Component */}
      <div className="mt-8">
        <SampleFetch />
      </div>
    </div>
  );
}
