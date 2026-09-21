"use client";

import Link from "next/link";
import { useState } from "react";
import { WordMark } from "@/components/brand/wordmark";
import { API_ROOT } from "@/lib/api/base";
import { Button } from "@/components/ui/button";

export default function DemoPage() {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function start() {
    setBusy(true);
    setError("");
    try {
      const response = await fetch(`${API_ROOT}/demo/session`, {
        method: "POST",
        credentials: "include",
      });
      const data = await response.json();
      if (!response.ok)
        throw new Error(data.error?.message || "Could not start the demo.");
      sessionStorage.setItem("draftwise-demo-workspace", data.workspace_id);
      location.assign("/dashboard");
    } catch (err) {
      setError((err as Error).message);
      setBusy(false);
    }
  }

  return (
    <div
      style={{
        minHeight: "100vh",
        background: "var(--surface)",
        display: "flex",
        flexDirection: "column",
      }}
    >
      {/* Minimal header */}
      <header
        style={{
          padding: "16px 24px",
          borderBottom: "1px solid var(--border)",
          background: "white",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
        }}
      >
        <Link href="/" aria-label="DraftWise home">
          <WordMark size="sm" />
        </Link>
        <Link
          href="/"
          style={{ fontSize: 13, color: "var(--ink-600)", textDecoration: "none" }}
        >
          Back to product info
        </Link>
      </header>

      {/* Main content */}
      <main
        id="main-content"
        style={{
          flex: 1,
          maxWidth: 760,
          width: "100%",
          margin: "0 auto",
          padding: "56px 24px",
        }}
      >
        <h1
          style={{
            fontSize: "clamp(28px, 4vw, 42px)",
            marginTop: 12,
            lineHeight: 1.2,
            letterSpacing: "-0.02em",
          }}
        >
          Every draft checked.
          <br />
          Every change explained.
        </h1>
        <p
          style={{
            marginTop: 16,
            fontSize: 17,
            color: "var(--ink-600)",
            lineHeight: 1.65,
            maxWidth: 540,
          }}
        >
          Explore 520 provided emails and 250 shipping documents in an isolated
          sample workspace. No account or credit card required.
        </p>

        {/* Steps */}
        <div
          style={{
            margin: "36px 0",
            padding: "24px",
            borderTop: "1px solid var(--border)",
            borderBottom: "1px solid var(--border)",
          }}
        >
          <p
            style={{
              fontSize: 13,
              fontWeight: 600,
              color: "var(--ink-600)",
              marginBottom: 16,
            }}
          >
            A guided starting point:
          </p>
          <ol
            style={{
              listStyle: "none",
              padding: 0,
              margin: 0,
              display: "flex",
              flexDirection: "column",
              gap: 14,
            }}
          >
            {[
              "Open email_001 in the Inbox. Read the amendment request and choose Open amendment case.",
              "Select the sample shipping instruction and draft BL after extraction finishes.",
              "Inspect all seven comparison fields with their source evidence, then preview a correction.",
              "Return to the dashboard to see alerts, the review queue, and the Ask DraftWise assistant.",
            ].map((step, i) => (
              <li
                key={i}
                style={{
                  display: "flex",
                  gap: 14,
                  fontSize: 14,
                  color: "var(--ink-700)",
                  lineHeight: 1.6,
                }}
              >
                <span
                  style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    width: 26,
                    height: 26,
                    borderRadius: "50%",
                    background: "var(--brand-100)",
                    color: "var(--brand-800)",
                    fontWeight: 700,
                    fontSize: 13,
                    flexShrink: 0,
                    marginTop: 1,
                  }}
                >
                  {i + 1}
                </span>
                {step}
              </li>
            ))}
          </ol>
        </div>

        {/* What's available in the demo */}
        <div style={{ marginBottom: 32 }}>
          <p
            style={{
              fontSize: 13,
              fontWeight: 600,
              color: "var(--ink-700)",
              marginBottom: 12,
            }}
          >
            Everything you can explore:
          </p>
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fill, minmax(200px, 1fr))",
              gap: 8,
            }}
          >
            {[
              "Email classification (5 categories)",
              "Seven-field document comparison",
              "Source evidence for every field",
              "Human review queue",
              "Amendment timeline",
              "Returned-draft re-check",
              "Spam and phishing alerts",
              "Concept drift monitoring",
              "Ask DraftWise assistant",
              "Customisable dashboard",
            ].map((f) => (
              <div
                key={f}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 8,
                  fontSize: 13,
                  color: "var(--ink-700)",
                  padding: "8px 12px",
                  border: "1px solid var(--border)",
                  borderRadius: "var(--radius)",
                  background: "white",
                }}
              >
                <span
                  style={{ color: "var(--brand-800)", fontWeight: 700, fontSize: 12 }}
                >
                  ✓
                </span>
                {f}
              </div>
            ))}
          </div>
        </div>

        {/* Limitations notice */}
        <p
          style={{
            fontSize: 13,
            color: "var(--ink-400)",
            marginBottom: 28,
            lineHeight: 1.6,
            padding: "12px 16px",
            background: "white",
            border: "1px solid var(--border)",
            borderRadius: "var(--radius)",
          }}
        >
          This demo uses the supplied sample emails and attachments.
          Run a bounded AI review without signing in. Each result identifies AI,
          deterministic rules or timeout fallback. Simulate Gmail fetch imports
          prepared samples and does not connect Google. Sessions expire after
          8 hours; expired sample data is eligible for cleanup after a short
          processing grace period. Anonymous session metadata and audit history
          remain. Uploaded files require administrator cleanup. Do not upload
          confidential material into the demo.
        </p>

        {/* CTA */}
        <div style={{ display: "flex", alignItems: "center", gap: 20, flexWrap: "wrap" }}>
          <Button
            size="md"
            onClick={start}
            disabled={busy}
            className="px-7 py-3 text-base"
            tip={{ name: "Start the demo", description: "Opens an isolated sample workspace with 520 emails; no account needed" }}
          >
            {busy ? "Preparing your workspace…" : "Start the demo"}
          </Button>
          <Link
            href="/sign-in"
            style={{ fontSize: 14, color: "var(--ink-600)", textDecoration: "underline" }}
          >
            Use my account instead
          </Link>
        </div>

        {error && (
          <p role="alert" className="alert-error" style={{ marginTop: 16 }}>
            {error}
          </p>
        )}
      </main>
    </div>
  );
}
