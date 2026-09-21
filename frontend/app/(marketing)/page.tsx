import type { Metadata } from "next";
import Link from "next/link";
import Image from "next/image";
import { DocumentPreview } from "@/components/brand/document-preview";

export const metadata: Metadata = {
  title: { absolute: "DraftWise | Shipping document verification" },
  description:
    "Compare shipping instructions with draft bills of lading across seven critical fields. Inspect source evidence, track carrier amendments, and verify returned revisions with DraftWise.",
  alternates: { canonical: "/" },
};

export default function Landing() {
  return (
    <>
      {/* ── Hero ─────────────────────────────────────────────── */}
      <section className="business-hero">
        <div className="business-hero-copy">
          <p className="hero-eyebrow">Shipping Document Verification</p>
          <h1>Check shipping drafts before mistakes travel further.</h1>
          <p>
            Compare a draft Bill of Lading against its Shipping Instructions
            across seven critical fields. See what differs, inspect the
            source evidence, and verify returned carrier revisions — all in
            one workspace.
          </p>
          <div className="business-actions">
            <Link href="/demo" className="btn-primary">
              Try the demo
            </Link>
            <Link href="/workflow" className="business-text-link">
              See how it works <span aria-hidden="true">→</span>
            </Link>
          </div>
          <small>
            No sign-in required. Self-contained sandbox with sample shipment
            data.
          </small>
        </div>
        <DocumentPreview />
      </section>

      {/* ── Promise bar ──────────────────────────────────────── */}
      <div className="business-promise">
        <strong>Seven fields. Every draft. Every revision.</strong>
        <span>Source evidence. Amendment tracking. Regression checks.</span>
      </div>

      {/* ── Seven fields section ─────────────────────────────── */}
      <section className="business-section business-fields-section">
        <div className="business-section-intro">
          <h2>Seven fields that matter most.</h2>
          <p>
            Every comparison checks the same canonical fields between the
            Shipping Instructions and the carrier&apos;s draft Bill of Lading.
            Discrepancies are flagged with source evidence — not assumptions.
          </p>
        </div>
        <div className="fields-grid">
          {[
            {
              field: "Shipper",
              desc: "Name and address of the exporting party",
            },
            {
              field: "Consignee",
              desc: "Receiving party as stated on the B/L",
            },
            {
              field: "Notify Party",
              desc: "Party to be notified upon cargo arrival",
            },
            {
              field: "Port of Loading",
              desc: "Disambiguated from section labels and directional cues",
            },
            {
              field: "Port of Discharge",
              desc: "Verified against SI regardless of carrier terminology",
            },
            {
              field: "Container Count",
              desc: "Numeric comparison with tabular precision",
            },
            {
              field: "Gross Weight",
              desc: "Kilogram values with unit conversion awareness",
            },
          ].map(({ field, desc }) => (
            <div key={field} className="field-card">
              <h3>{field}</h3>
              <p>{desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* ── Visual evidence section ──────────────────────────── */}
      <section className="business-section business-evidence">
        <div>
          <h2>
            The shipment moves forward.
            <br />
            The paperwork should too.
          </h2>
          <p>
            Keep the original Shipping Instructions and draft Bill of Lading
            together. Trace a difference to its source, prepare supported
            corrections, and verify what changed in the returned draft.
          </p>
          <Link href="/demo" className="business-text-link">
            Explore a sample case <span aria-hidden="true">→</span>
          </Link>
        </div>
        <div className="business-hero-visual">
          <Image
            src="/images/shipping-hero.webp"
            alt="Shipping containers at a cargo terminal — the physical cargo that depends on accurate documentation"
            width={1536}
            height={1024}
            loading="eager"
            sizes="(max-width: 800px) 100vw, 50vw"
          />
          <div className="business-caption">
            <span>FROM DOCUMENT TO DECISION</span>
            <strong>Every draft checked. Every change explained.</strong>
          </div>
        </div>
      </section>


      <section className="business-section business-process">
        <div className="business-section-intro">
          <h2>From inbox to verified draft.</h2>
          <p>
            Four stages. Each decision grounded in the source documents.
          </p>
        </div>
        <ol>
          {[
            [
              "Intake & Classification",
              "Emails are classified into five categories: B/L comparison requests, SI submissions, invoice queries, general correspondence, and spam. Only comparison requests proceed to field extraction.",
            ],
            [
              "Field Extraction",
              "Seven key fields are extracted from both the Shipping Instructions and the draft Bill of Lading using PDF, DOCX, and OCR parsers with grounded evidence coordinates.",
            ],
            [
              "Discrepancy Review",
              "Each field is compared and marked as Matched, Mismatch, Missing, or Uncertain. Ambiguous labels like 'Load Port' vs 'POL' are resolved through context-aware disambiguation.",
            ],
            [
              "Amendment Tracking",
              "When the carrier returns a revised draft, all seven fields are re-checked against the pinned SI. Fixed fields are confirmed; new regressions are immediately flagged.",
            ],
          ].map(([title, body], i) => (
            <li key={title}>
              <span>0{i + 1}</span>
              <h3>{title}</h3>
              <p>{body}</p>
            </li>
          ))}
        </ol>
      </section>

      {/* ── Trust / design principles ────────────────────────── */}
      <section className="business-section business-trust">
        <h2>Built around the operator&apos;s decision.</h2>
        <div>
          <article>
            <h3>Evidence before confidence</h3>
            <p>
              Every comparison decision links to the exact source span in the
              original document. A missing value stays missing — it never
              becomes an assumed match.
            </p>
          </article>
          <article>
            <h3>Visible amendment history</h3>
            <p>
              Track every round of carrier revisions. See which corrections were
              applied and which regressions were introduced in the returned
              draft.
            </p>
          </article>
          <article>
            <h3>Honest limits</h3>
            <p>
              Extraction accuracy depends on document quality and format.
              Uncertain classifications are routed to human review — never
              auto-resolved. Scanned or handwritten documents may require
              manual verification.
            </p>
          </article>
        </div>
      </section>

      {/* ── Closing CTA ──────────────────────────────────────── */}
      <section className="business-closing">
        <div>
          <h2>See it in action with real shipment data.</h2>
          <p>
            Walk through the full verification workflow in a self-contained
            sandbox. No account, no setup — sample cases are pre-loaded and
            ready to inspect.
          </p>
        </div>
        <Link href="/demo" className="btn-primary">
          Open the demo
        </Link>
      </section>
    </>
  );
}
