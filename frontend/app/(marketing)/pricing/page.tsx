import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Pricing",
  description:
    "DraftWise pricing: free no-account demo with sample shipment data, and pilot access for teams.",
  alternates: {
    canonical: `${process.env.SITE_URL || "http://localhost:3000"}/pricing`,
  },
};

export default function PricingPage() {
  return (
    <div style={{ maxWidth: 900, margin: "0 auto", padding: "56px 24px" }}>
      <h1 style={{ fontSize: 36, marginTop: 12 }}>Simple, honest pricing</h1>
      <p className="page-description" style={{ marginBottom: 48 }}>
        Start with the free demo. Everything you need to evaluate the full
        verification workflow.
      </p>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))",
          gap: 24,
        }}
      >
        {/* Free demo tier */}
        <div
          className="card"
          style={{ padding: "32px", display: "flex", flexDirection: "column" }}
        >
          <p className="pricing-tier-label">Free</p>
          <h2 style={{ fontSize: 24, marginTop: 8 }}>Sample demo</h2>
          <p className="pricing-price">$0</p>
          <p className="pricing-note">No account required</p>

          <ul className="pricing-features">
            {[
              "Sample shipment emails and documents",
              "Seven-field SI vs B/L comparison",
              "Full amendment and revision workflow",
              "Source evidence inspection",
              "Five-category email classification",
              "Drift and phishing signal alerts",
              "Self-contained sandbox environment",
              "Session expires after 8 hours",
            ].map((f) => (
              <li key={f}>
                <span className="pricing-check">✓</span>
                {f}
              </li>
            ))}
          </ul>

          <Link href="/demo" className="pricing-cta-primary">
            Start demo
          </Link>
        </div>

        {/* Pilot tier */}
        <div
          className="card"
          style={{
            padding: "32px",
            display: "flex",
            flexDirection: "column",
            borderColor: "var(--brand-700)",
          }}
        >
          <p className="pricing-tier-label">Team</p>
          <h2 style={{ fontSize: 24, marginTop: 8 }}>Pilot access</h2>
          <p
            style={{
              marginTop: 4,
              fontSize: 18,
              fontWeight: 600,
              color: "var(--ink-600)",
            }}
          >
            Available upon request
          </p>
          <p className="pricing-note">
            Terms discussed directly — no hidden commitments
          </p>

          <ul className="pricing-features">
            {[
              "Everything in the demo",
              "Gmail inbox connection (read-only; in development, not yet available)",
              "Persistent workspace and case history",
              "Team roles (admin, reviewer, viewer)",
              "Custom equivalence rules",
              "Usage and cost transparency",
            ].map((f) => (
              <li key={f}>
                <span className="pricing-check">✓</span>
                {f}
              </li>
            ))}
          </ul>

          <Link href="/demo" className="pricing-cta-secondary">
            Explore demo first
          </Link>
        </div>
      </div>

      <div className="pricing-disclaimer">
        <strong>No invented commitments:</strong> Paid amounts, currencies,
        refund terms and usage quotas will be agreed directly before any
        contract. Completed checks confirm document consistency; they do not
        authorize cargo release or constitute a professional legal opinion.
      </div>
    </div>
  );
}
