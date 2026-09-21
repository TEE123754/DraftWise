"use client";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api/client";
import { useAuth } from "@/components/auth-provider";
import { StatusBadge } from "@/components/cases/status-badge";
import { DashboardPanels, type ExtraSummary } from "@/components/dashboard-panels";
import { ReadingProgress } from "@/components/reading-progress";
import type { CaseSummary } from "@/lib/api/types";
import { Button } from "@/components/ui/button";

type Summary = ExtraSummary & {
  emails_total: number;
  emails_classified: number;
  cases_open: number;
  cases_checked: number;
  cases_failed: number;
  review_queue_size: number;
  awaiting_revision: number;
  jobs_in_progress: number;
  last_updated: string;
};
export default function Dashboard() {
  const auth = useAuth();
  const [data, setData] = useState<Summary | null>(null);
  const [cases, setCases] = useState<CaseSummary[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const load = useCallback(async (signal?: AbortSignal) => {
    setLoading(true);
    setError("");
    try {
      const [summary, queue] = await Promise.all([
        api<Summary>("/dashboard", { signal }),
        api<{ items: CaseSummary[] }>(
          "/cases?readiness=needs_decision&readiness=changes_required&limit=6",
          { signal },
        ),
      ]);
      if (!signal?.aborted) {
        setData(summary);
        setCases(queue.items);
      }
    } catch (e) {
      if (!signal?.aborted) {
        setError((e as Error).message);
        setData(null);
        setCases([]);
      }
    } finally {
      if (!signal?.aborted) setLoading(false);
    }
  }, []);
  useEffect(() => {
    if (!auth.ready || !auth.workspace) return;
    const controller = new AbortController();
    void load(controller.signal);
    return () => controller.abort();
  }, [auth.ready, auth.workspace, load]);
  const stages = data
    ? ([
        [
          "Emails imported",
          data.emails_total,
          "/inbox",
          `${data.emails_classified} classified`,
        ],
        [
          "Open cases",
          data.cases_open,
          "/cases?open=true",
          "Documents being checked",
        ],
        [
          "Awaiting revision",
          data.awaiting_revision,
          "/cases?readiness=awaiting_revision",
          "Returned draft needed",
        ],
        ["Checked", data.cases_checked, "/completed", "All seven fields match"],
      ] as const)
    : [];
  return (
    <>
      <header className="overview-heading">
        <div>
          <h1>Overview</h1>
          <p className="page-description">
            Your shipping documents, from incoming request to checked draft.
          </p>
        </div>
        <div className="overview-actions">
          <Button
            variant="secondary"
            disabled={loading || !auth.workspace}
            onClick={() => void load()}
            tip={{ name: "Refresh", description: "Reloads the counts and the work queue" }}
          >
            Refresh
          </Button>
          <Link href="/inbox" className="btn-primary">
            Open inbox
          </Link>
        </div>
      </header>
      <ReadingProgress />
      {error ? (
        <section role="alert" className="alert-error">
          <h2>Workspace summary unavailable</h2>
          <p>{error}</p>
          <p>No sample counts have been substituted. Use Refresh to retry.</p>
        </section>
      ) : loading ? (
        <p role="status">Loading workspace summary…</p>
      ) : (
        data && (
          <>
            <section aria-label="Workspace summary" className="shipment-flow">
              {stages.map(([label, value, href, caption], index) => (
                <Link href={href} key={label}>
                  <span className="flow-step">
                    <span aria-hidden="true">0{index + 1} / </span>
                    <span>{label}</span>
                  </span>
                  <strong>{value.toLocaleString()}</strong>
                  <small>{caption}</small>
                </Link>
              ))}
            </section>
            <div className="operations-layout" style={{gridTemplateColumns:"1fr"}}>
              <section className="decision-desk">
                <div className="desk-heading">
                  <div>
                    <h2>Cases needing action</h2>
                    <p>Open the evidence, then decide the next change.</p>
                  </div>
                  <Link href="/cases">View all cases ↗</Link>
                </div>
                {cases.length ? (
                  <ul>
                    {cases.map((item) => (
                      <li key={item.id}>
                        <Link href={`/cases/${item.id}`}>
                          <div className="case-ledger-top">
                            <strong>{item.reference}</strong>
                            <StatusBadge status={item.readiness} />
                          </div>
                          <p>{item.next_action.title}</p>
                          <div className="case-ledger-bottom">
                            <span>
                              {item.open_issue_count} open{" "}
                              {item.open_issue_count === 1 ? "issue" : "issues"}
                            </span>
                            <span>
                              Review documents <span aria-hidden="true">↗</span>
                            </span>
                          </div>
                        </Link>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <div className="desk-empty">
                    <h3>No decisions waiting here.</h3>
                    <p>
                      Other cases may still need documents or processing. Start
                      with an email to compare its shipping instructions and
                      draft.
                    </p>
                    <Link href="/inbox" className="btn-secondary">
                      Browse incoming emails
                    </Link>
                  </div>
                )}
              </section>
  
            </div>
            <DashboardPanels data={data}/>
          <footer className="workspace-update">
              <span>
                Updated {new Date(data.last_updated).toLocaleString()}
              </span>
              <Link href="/alerts">
                Inspect safety and drift alerts
              </Link>
            </footer>
          </>
        )
      )}
    </>
  );
}
