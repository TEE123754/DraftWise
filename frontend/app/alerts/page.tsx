"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { api, post } from "@/lib/api/client";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/components/auth-provider";
type Alert = {
  id: string;
  alert_type: string;
  title: string;
  description: string;
  lifecycle: string;
  sample_email_ids: string[];
  baseline_version?: string;
  changed_features?: unknown[];
  investigation_note?: string;
  resolved_reason?: string;
};
export default function Alerts() {
  const auth = useAuth();
  const [alerts, setAlerts] = useState<Alert[]>([]),
    [error, setError] = useState(""),
    [loading, setLoading] = useState(true);
  async function load() {
    try {
      setAlerts((await api<{ items: Alert[] }>("/alerts")).items);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }
  useEffect(() => {
    void load();
  }, []);
  return (
    <>
      <Link href="/dashboard">Overview</Link>
      <h1 className="text-2xl font-semibold mt-4">Alerts</h1>
      <p className="mt-2">
        Review the source email and record your reason. Safety signals and
        distribution shifts require investigation.
      </p>
      {error && (
        <p role="alert" className="mt-4">
          {error}
        </p>
      )}
      {loading && <p role="status">Loading alerts…</p>}
      {!loading && !error && !alerts.length && (
        <p className="mt-4">No alerts in this workspace.</p>
      )}
      <div className="mt-5 space-y-4">
        {alerts.map((a) => (
          <AlertCard
            key={a.id}
            alert={a}
            canAct={["admin", "reviewer"].includes(auth.role)}
            reload={load}
          />
        ))}
      </div>
    </>
  );
}
function AlertCard({
  alert,
  canAct,
  reload,
}: {
  alert: Alert;
  canAct: boolean;
  reload: () => Promise<void>;
}) {
  const [reason, setReason] = useState(""),
    [category, setCategory] = useState("GENERAL"),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  const open = !["resolved", "dismissed"].includes(alert.lifecycle);
  async function act(action: string) {
    setBusy(true);
    setError("");
    try {
      await post(`/alerts/${alert.id}/action`, { action, category, reason });
      await reload();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <article className="card p-5">
      <h2 className="text-lg font-semibold">{alert.title}</h2>
      <p className="text-sm mt-1">
        {alert.alert_type === "drift"
          ? "Suspected distribution shift"
          : alert.alert_type}{" "}
        · {alert.lifecycle}
      </p>
      <p className="mt-2">{alert.description}</p>
      <div className="flex flex-wrap gap-3 mt-3">
        {alert.sample_email_ids.map((id, i) => (
          <Link key={id} href={`/inbox/${id}`} className="underline">
            Review source email {i + 1}
          </Link>
        ))}
      </div>
      {alert.baseline_version && (
        <p className="text-sm mt-3 break-all">
          Baseline: {alert.baseline_version}
        </p>
      )}
      {alert.changed_features?.length ? (
        <details className="mt-3">
          <summary>Monitoring evidence and window sizes</summary>
          <pre className="text-xs whitespace-pre-wrap break-words">
            {JSON.stringify(alert.changed_features, null, 2)}
          </pre>
        </details>
      ) : null}
      {(alert.investigation_note || alert.resolved_reason) && (
        <p className="mt-3 text-sm">
          Review note: {alert.investigation_note || alert.resolved_reason}
        </p>
      )}
      {open && canAct && (
        <>
          <label className="block mt-4 text-sm">
            Reason and investigation findings
            <textarea
              className="input mt-1"
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              maxLength={1000}
            />
          </label>
          {alert.alert_type !== "drift" && (
            <label className="block mt-3 text-sm">
              Category if this is not spam
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
                ].map((c) => (
                  <option key={c}>{c}</option>
                ))}
              </select>
            </label>
          )}
          <div className="flex flex-wrap gap-3 mt-4">
            <Button
              variant="outline"
              disabled={busy || reason.trim().length < 5}
              onClick={() => void act("investigate")}
            >
              Record investigation
            </Button>
            {alert.alert_type !== "drift" && (
              <>
                <Button
                  disabled={busy || reason.trim().length < 5}
                  onClick={() => void act("not_spam")}
                >
                  Mark not spam and release
                </Button>
                <Button
                  variant="outline"
                  disabled={busy || reason.trim().length < 5}
                  onClick={() => void act("confirm_spam")}
                >
                  Confirm spam and move to Trash
                </Button>
              </>
            )}
            <Button
              variant="outline"
              disabled={busy || reason.trim().length < 5}
              onClick={() => void act("resolve")}
            >
              Resolve alert
            </Button>
          </div>
          {alert.alert_type === "drift" && (
            <div className="mt-3">
              <p className="text-sm">
                Review and relabel the source emails before replacing a
                baseline. At least 20 reviewed labels are required.
              </p>
              <Button
                className="mt-2"
                disabled={busy || reason.trim().length < 5}
                onClick={async () => {
                  setBusy(true);
                  setError("");
                  try {
                    await post("/quality/baseline", {});
                    await act("investigate");
                  } catch (e) {
                    setError((e as Error).message);
                  } finally {
                    setBusy(false);
                  }
                }}
              >
                Create baseline from reviewed labels
              </Button>
            </div>
          )}
        </>
      )}
      {error && (
        <p role="alert" className="mt-3">
          {error}
        </p>
      )}
    </article>
  );
}
