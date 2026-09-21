"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api } from "@/lib/api/client";
import { Breadcrumbs } from "@/components/navigation/breadcrumbs";
import type { CaseSummary } from "@/lib/api/types";

export default function ReviewPage() {
  const [items, setItems] = useState<CaseSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    api<{ items: CaseSummary[] }>("/cases?readiness=needs_decision")
      .then((r) => setItems(r.items))
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  return (
    <>
      <Breadcrumbs items={[{ label: "Overview", href: "/dashboard" }, { label: "Review" }]} />

      <header style={{ marginBottom: 28 }}>
        <h1 style={{ fontSize: 26 }}>Human review queue</h1>
        <p className="page-description">
          Cases awaiting a human decision. Inspect the source evidence before
          deciding which documents and supported corrections to use.
        </p>
      </header>

      <div
        style={{
          padding: "14px 18px",
          background: "var(--surface)",
          border: "1px solid var(--border)",
          borderRadius: "var(--radius)",
          fontSize: 13,
          color: "var(--ink-600)",
          lineHeight: 1.6,
          marginBottom: 24,
        }}
      >
        <strong style={{ color: "var(--ink-900)" }}>How review works:</strong>{" "}
        Open a case to inspect its fields and source evidence. Confirm SI and BL
        sources and preview supported correction requests. Open a field's evidence
        to review its extracted value, cite supporting text and rerun comparison.
      </div>

      {error && (
        <p role="alert" className="alert-error" style={{ marginBottom: 16 }}>
          {error}
        </p>
      )}

      <div className="card" style={{ overflow: "hidden" }}>
        {loading ? (
          <div style={{ padding: 24 }}>
            {[1, 2, 3].map((i) => (
              <div
                key={i}
                className="skeleton"
                style={{ height: 56, borderRadius: "var(--radius)", marginBottom: 10 }}
              />
            ))}
          </div>
        ) : error ? <p style={{padding:24}}>The review queue could not be loaded. Refresh to retry.</p> : items.length === 0 ? (
          <div
            style={{
              padding: "48px 24px",
              textAlign: "center",
            }}
          >
            <p
              style={{ fontSize: 32, color: "var(--status-green)", marginBottom: 12 }}
              aria-hidden="true"
            >
              ✓
            </p>
            <p style={{ fontWeight: 600, fontSize: 15, color: "var(--ink-900)" }}>
              Review queue is empty
            </p>
            <p style={{ fontSize: 13, color: "var(--ink-600)", marginTop: 6 }}>
              No cases are waiting for a human decision right now.
            </p>
          </div>
        ) : (
          <ul style={{ listStyle: "none", margin: 0, padding: 0 }}>
            <li
              style={{
                padding: "10px 20px",
                background: "var(--surface)",
                borderBottom: "1px solid var(--border)",
                display: "grid",
                gridTemplateColumns: "1fr auto auto",
                gap: 16,
                fontSize: 11,
                fontWeight: 700,
                color: "var(--ink-400)",
                letterSpacing: "0.08em",
                textTransform: "uppercase",
              }}
            >
              <span>Case</span>
              <span>Open issues</span>
              <span></span>
            </li>
            {items.map((item, i) => (
              <li
                key={item.id}
                style={{ borderTop: i > 0 ? "1px solid var(--border)" : "none" }}
              >
                <Link
                  href={`/cases/${item.id}`}
                  style={{
                    display: "grid",
                    gridTemplateColumns: "1fr auto auto",
                    alignItems: "center",
                    gap: 16,
                    padding: "14px 20px",
                    textDecoration: "none",
                  }}
                >
                  <div>
                    <p style={{ fontWeight: 600, fontSize: 14, color: "var(--ink-900)" }}>
                      {item.reference}
                    </p>
                    <p style={{ fontSize: 13, color: "var(--ink-600)", marginTop: 2 }}>
                      {item.next_action.title}
                    </p>
                  </div>
                  <span
                    style={{
                      fontSize: 13,
                      fontWeight: 600,
                      color:
                        item.open_issue_count > 0
                          ? "var(--status-amber)"
                          : "var(--ink-400)",
                    }}
                  >
                    {item.open_issue_count}
                  </span>
                  <span style={{ fontSize: 13, color: "var(--brand-800)", fontWeight: 500 }}>
                    Review
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </div>

      <p style={{ marginTop: 20, fontSize: 12, color: "var(--ink-400)" }}>
        A confirmed correction updates the comparison and is recorded in the
        amendment timeline. Original extracted values are preserved.
      </p>
    </>
  );
}
