"use client";

import { useCallback, useEffect, useState } from "react";
import {
  CheckCircle2,
  Plus,
  RotateCcw,
  ShieldAlert,
  ShieldCheck,
  XCircle,
} from "lucide-react";
import { api, post } from "@/lib/api/client";
import type { EquivalenceRuleItem, FieldName } from "@/lib/api/types";
import { label } from "@/lib/utils";
import { useAuth } from "@/components/auth-provider";
import { Button } from "@/components/ui/button";

const RULE_FIELDS: FieldName[] = [
  "shipper",
  "consignee",
  "notify_party",
  "port_of_loading",
  "port_of_discharge",
];

export default function RulesPage() {
  const auth = useAuth();
  const canManage = ["reviewer", "admin", "operator"].includes(auth.role);
  const [rules, setRules] = useState<EquivalenceRuleItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [stateFilter, setStateFilter] = useState<string>("all");
  const [creating, setCreating] = useState(false);
  const [revokingId, setRevokingId] = useState<string | null>(null);
  const [revokeRationale, setRevokeRationale] = useState("");
  const [busy, setBusy] = useState("");

  const loadRules = useCallback(async () => {
    try {
      const q = stateFilter !== "all" ? `?state=${stateFilter}` : "";
      const res = await api<{ items: EquivalenceRuleItem[] }>(`/rules${q}`);
      setRules(res.items);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  }, [stateFilter]);

  useEffect(() => {
    void loadRules();
  }, [loadRules]);

  async function handleApprove(ruleId: string) {
    setBusy(`Approving rule…`);
    setError("");
    setSuccess("");
    try {
      await post(`/rules/${ruleId}/approve`, {});
      setSuccess("Rule approved successfully. It is now active for downstream verification.");
      await loadRules();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy("");
    }
  }

  async function handleRevoke(event: React.FormEvent) {
    event.preventDefault();
    if (!revokingId) return;
    setBusy("Revoking rule…");
    setError("");
    setSuccess("");
    try {
      const res = await post<{ stale_reports_count: number }>(`/rules/${revokingId}/revoke`, {
        rationale: revokeRationale,
      });
      setSuccess(
        `Rule revoked. ${res.stale_reports_count || 0} downstream case(s) marked for re-verification.`
      );
      setRevokingId(null);
      setRevokeRationale("");
      await loadRules();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy("");
    }
  }

  async function handleCreate(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setSuccess("");
    const form = new FormData(event.currentTarget);
    setBusy("Creating equivalence rule…");
    try {
      // Find a case id or use a fallback case id from recent cases
      const casesRes = await api<{ items: { id: string }[] }>("/cases?limit=1");
      const caseId = casesRes.items[0]?.id;
      if (!caseId) {
        throw new Error("Create at least one shipment case before adding customer rules.");
      }
      await post(`/cases/${caseId}/rules`, {
        field: form.get("field"),
        left_value: form.get("left_value"),
        right_value: form.get("right_value"),
        rationale: form.get("rationale"),
        auto_approve: form.get("auto_approve") === "on",
      });
      setSuccess("Equivalence rule created and applied.");
      setCreating(false);
      await loadRules();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy("");
    }
  }

  const approvedCount = rules.filter((r) => r.state === "approved").length;
  const proposedCount = rules.filter((r) => r.state === "proposed").length;
  const revokedCount = rules.filter((r) => r.state === "revoked").length;

  return (
    <div className="mx-auto max-w-5xl py-6">
      <header className="flex flex-col justify-between gap-4 sm:flex-row sm:items-center">
        <div>
          <h1 className="text-3xl font-semibold text-slate-900">
            Equivalence Rules
          </h1>
          <p className="mt-2 text-sm text-slate-600">
            Approved entity and port aliases that reconcile legitimate naming differences across documents.
          </p>
        </div>
        <Button
          disabled={!canManage || Boolean(busy)}
          onClick={() => setCreating(!creating)}
        >
          <Plus size={16} className="mr-1.5" />
          {creating ? "Close Form" : "New Rule"}
        </Button>
      </header>

      {/* Stats Summary */}
      <div className="mt-6 grid grid-cols-1 gap-4 sm:grid-cols-3">
        <div className="card flex items-center gap-4 p-5">
          <div className="rounded-lg bg-emerald-50 p-3 text-emerald-700">
            <ShieldCheck size={24} />
          </div>
          <div>
            <p className="text-2xl font-bold text-slate-900">{approvedCount}</p>
            <p className="text-xs font-medium text-slate-500">Active Approved Rules</p>
          </div>
        </div>
        <div className="card flex items-center gap-4 p-5">
          <div className="rounded-lg bg-amber-50 p-3 text-amber-700">
            <ShieldAlert size={24} />
          </div>
          <div>
            <p className="text-2xl font-bold text-slate-900">{proposedCount}</p>
            <p className="text-xs font-medium text-slate-500">Proposed / Pending Review</p>
          </div>
        </div>
        <div className="card flex items-center gap-4 p-5">
          <div className="rounded-lg bg-slate-100 p-3 text-slate-600">
            <XCircle size={24} />
          </div>
          <div>
            <p className="text-2xl font-bold text-slate-900">{revokedCount}</p>
            <p className="text-xs font-medium text-slate-500">Revoked Rules</p>
          </div>
        </div>
      </div>

      {error && (
        <div role="alert" className="mt-5 rounded-lg bg-red-50 p-4 text-sm text-red-800">
          {error}
        </div>
      )}
      {success && (
        <div role="status" className="mt-5 rounded-lg bg-emerald-50 p-4 text-sm text-emerald-800">
          {success}
        </div>
      )}

      {/* Creation Modal / Form */}
      {creating && (
        <form onSubmit={handleCreate} className="card mt-6 p-6">
          <h2 className="text-lg font-semibold text-slate-900">
            Define New Equivalence Rule
          </h2>
          <p className="mt-1 text-xs text-slate-500">
            Equivalences are scoped to customer workspaces and audited with exact source evidence.
          </p>
          <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div>
              <label className="text-xs font-semibold text-slate-700">Field Scope</label>
              <select name="field" className="input mt-1" required defaultValue="shipper">
                {RULE_FIELDS.map((f) => (
                  <option key={f} value={f}>
                    {label(f)}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="text-xs font-semibold text-slate-700">Auto-Approve for Verification</label>
              <div className="mt-2 flex items-center gap-2">
                <input
                  type="checkbox"
                  name="auto_approve"
                  id="auto_approve"
                  defaultChecked
                  className="h-4 w-4 rounded border-slate-300 text-brand-600"
                />
                <label htmlFor="auto_approve" className="text-xs text-slate-600">
                  Activate rule immediately upon saving
                </label>
              </div>
            </div>
            <div>
              <label className="text-xs font-semibold text-slate-700">Left Identity (e.g. on SI)</label>
              <input
                name="left_value"
                className="input mt-1"
                placeholder="Example Export Limited"
                required
                maxLength={4000}
              />
            </div>
            <div>
              <label className="text-xs font-semibold text-slate-700">Right Identity (e.g. on BL)</label>
              <input
                name="right_value"
                className="input mt-1"
                placeholder="Example Export Ltd"
                required
                maxLength={4000}
              />
            </div>
            <div className="sm:col-span-2">
              <label className="text-xs font-semibold text-slate-700">Rationale / Customer Confirmation</label>
              <textarea
                name="rationale"
                className="input mt-1 min-h-20"
                placeholder="Confirmed identical corporate entity via commercial registration and customer email confirmation."
                required
                minLength={5}
                maxLength={1000}
              />
            </div>
          </div>
          <div className="mt-5 flex justify-end gap-3">
            <Button variant="outline" type="button" onClick={() => setCreating(false)}>
              Cancel
            </Button>
            <Button disabled={Boolean(busy)}>
              {busy || "Create Rule"}
            </Button>
          </div>
        </form>
      )}

      {/* Revocation Confirmation Dialog */}
      {revokingId && (
        <form onSubmit={handleRevoke} className="card mt-6 border-amber-200 bg-amber-50/50 p-6">
          <h2 className="text-base font-semibold text-amber-900">
            Revoke Equivalence Rule
          </h2>
          <p className="mt-1 text-xs text-amber-800">
            Revoking will cascade to downstream decisions: any cases using this rule will be marked stale and scheduled for re-verification.
          </p>
          <div className="mt-3">
            <label className="text-xs font-semibold text-slate-700">Reason for Revocation</label>
            <textarea
              value={revokeRationale}
              onChange={(e) => setRevokeRationale(e.target.value)}
              className="input mt-1"
              placeholder="e.g. Customer stated this alias is no longer valid for new bookings."
              required
              minLength={5}
              maxLength={1000}
            />
          </div>
          <div className="mt-4 flex justify-end gap-3">
            <Button variant="outline" type="button" onClick={() => setRevokingId(null)}>
              Cancel
            </Button>
            <Button
              type="submit"
              className="bg-red-600 text-white hover:bg-red-700"
              disabled={Boolean(busy)}
            >
              {busy || "Confirm Revocation"}
            </Button>
          </div>
        </form>
      )}

      {/* Filter Tabs */}
      <div className="mt-6 flex items-center gap-2 border-b border-slate-200 pb-3">
        {["all", "approved", "proposed", "revoked"].map((st) => (
          <Button
            key={st}
            size="sm"
            variant={stateFilter === st ? "primary" : "secondary"}
            aria-pressed={stateFilter === st}
            onClick={() => setStateFilter(st)}
            className="rounded-full capitalize"
          >
            {st}
          </Button>
        ))}
      </div>

      {/* Rules Table / List */}
      <section className="card mt-4 overflow-hidden" aria-label="Equivalence Rules List">
        {loading ? (
          <p className="p-6 text-sm text-slate-500">Loading rules…</p>
        ) : !rules.length ? (
          <div className="p-12 text-center">
            <p className="text-sm font-medium text-slate-600">No equivalence rules found in this view.</p>
            <p className="mt-1 text-xs text-slate-600">
              Create a rule above to link known entity names or port abbreviations.
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-slate-200 bg-slate-50 text-xs font-medium text-slate-500 uppercase">
                <tr>
                  <th className="px-5 py-3">Field</th>
                  <th className="px-5 py-3">Equivalent Identities</th>
                  <th className="px-5 py-3">Status</th>
                  <th className="px-5 py-3">Created</th>
                  {canManage && <th className="px-5 py-3 text-right">Actions</th>}
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {rules.map((rule) => (
                  <tr key={rule.id} className="hover:bg-slate-50/80">
                    <td className="px-5 py-4 font-medium text-slate-800 capitalize">
                      {label(rule.field)}
                    </td>
                    <td className="px-5 py-4">
                      <div className="flex items-center gap-2">
                        <span className="font-semibold text-slate-900">{rule.left_value}</span>
                        <span className="text-slate-400">↔</span>
                        <span className="font-semibold text-brand-800">{rule.right_value}</span>
                      </div>
                    </td>
                    <td className="px-5 py-4">
                      <span
                        className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-medium capitalize ${
                          rule.state === "approved"
                            ? "bg-emerald-50 text-emerald-700"
                            : rule.state === "proposed"
                            ? "bg-amber-50 text-amber-700"
                            : "bg-slate-100 text-slate-500"
                        }`}
                      >
                        {rule.state === "approved" && <CheckCircle2 size={12} />}
                        {rule.state === "proposed" && <ShieldAlert size={12} />}
                        {rule.state === "revoked" && <RotateCcw size={12} />}
                        {rule.state}
                      </span>
                    </td>
                    <td className="px-5 py-4 text-xs text-slate-500">
                      {new Date(rule.created_at).toLocaleDateString()}
                    </td>
                    {canManage && (
                      <td className="px-5 py-4 text-right">
                        <div className="flex items-center justify-end gap-2">
                          {rule.state === "proposed" && (
                            <Button
                              variant="outline"
                              className="h-8 px-3 text-xs"
                              onClick={() => handleApprove(rule.id)}
                              disabled={Boolean(busy)}
                            >
                              Approve
                            </Button>
                          )}
                          {rule.state === "approved" && (
                            <Button
                              variant="ghost"
                              className="h-8 px-3 text-xs text-red-600 hover:bg-red-50"
                              onClick={() => setRevokingId(rule.id)}
                              disabled={Boolean(busy)}
                            >
                              Revoke
                            </Button>
                          )}
                        </div>
                      </td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}
