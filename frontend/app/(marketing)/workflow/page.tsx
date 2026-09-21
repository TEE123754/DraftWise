import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "How DraftWise works",
  description:
    "A step-by-step explanation of the DraftWise shipping document verification workflow: intake, classification, documents, extraction, seven-field comparison and the reply.",
  alternates: {
    canonical: "/workflow",
  },
};

export default function WorkflowPage() {
  return (
    <div style={{ maxWidth: 800, margin: "0 auto", padding: "56px 24px" }}>
      <h1 style={{ fontSize: 36, marginTop: 12, marginBottom: 8 }}>
        How DraftWise works
      </h1>
      <p className="page-description" style={{ marginBottom: 40 }}>
        A text walkthrough of the complete verification cycle: from incoming
        email to verified returned draft.
      </p>

      <div className="prose">
        <h2>Step 1: Intake</h2>
        <p>
          An email with a shipment request arrives. You can add it yourself,
          or try the supplied sample mailbox in the demo. DraftWise reads the
          sender, subject, body (quoted history is kept apart from the current
          message) and every attached document. Mail from a connected Gmail
          inbox is not available yet.
        </p>
        <p>
          Each email keeps its own ID (for example <code>email_007</code>) in
          every list, filter and link.
        </p>

        <h2>Step 2: Classify</h2>
        <p>The email is classified into one of five categories:</p>
        <ul>
          <li>
            <strong>BL Comparison</strong>: a request to compare a draft bill
            of lading against shipping instructions
          </li>
          <li>
            <strong>SI Request</strong>: the shipper is submitting or amending
            shipping instructions
          </li>
          <li>
            <strong>Invoice Query</strong>: a question about charges, not a
            document comparison
          </li>
          <li>
            <strong>General</strong>: correspondence that needs no document
            check
          </li>
          <li>
            <strong>Spam</strong>: unsolicited or irrelevant email, assessed
            separately for phishing signals
          </li>
        </ul>
        <p>
          Local rules decide first. The AI is used only when the rules cannot
          decide, or when you ask for it, and every AI call is counted against
          a daily budget. An identical email or document is never sent twice.
          An uncertain result is left for a person rather than guessed.
        </p>

        <h2>Step 3: Documents</h2>
        <p>
          A comparison needs both the shipping instructions (SI) and the draft
          bill of lading (BL). DraftWise tells you which documents it found and
          names any that are missing:
        </p>
        <ul>
          <li>The sender asks for the draft to be sent and attached nothing: it waits for the draft.</li>
          <li>The email says files are attached but none arrived: ask the sender to resend.</li>
          <li>Only the SI or only the BL arrived, or a file is the wrong type or unreadable: ask for the right one.</li>
        </ul>
        <p>
          A follow-up message is prepared from a template, ready to copy and
          edit. Nothing is sent for you. Where another email in your workspace
          cites the same booking or B/L reference, that document is suggested
          as a link, and it is attached only when you confirm.
        </p>

        <h2>Step 4: Extract</h2>
        <p>
          Seven fields are read from the SI and from the BL, each with its
          source quote:
        </p>
        <ul>
          <li>Shipper</li>
          <li>Consignee</li>
          <li>Notify party</li>
          <li>Port of loading</li>
          <li>Port of discharge</li>
          <li>Container count</li>
          <li>Gross weight (kg)</li>
        </ul>
        <p>
          Ambiguous words are settled from their surroundings: a loading port
          by its section label, gross weight apart from net weight by its
          units. Where that is not possible the field is marked for review.
        </p>

        <h2>Step 5: Compare</h2>
        <p>
          Each field is compared between the SI and the BL:{" "}
          <strong>Match</strong>, <strong>Mismatch</strong>,{" "}
          <strong>Missing</strong>, <strong>Partial match</strong> or{" "}
          <strong>Uncertain</strong>. The inbox shows the SI, the BL and what
          the email itself says side by side, so a difference is visible at a
          glance.
        </p>

        <h2>Step 6: Decide and reply</h2>
        <p>
          Mismatched or uncertain fields go to a reviewer, who can confirm a
          value against its source, correct it, or mark a document unreadable.
          DraftWise prepares a correction request listing only changes the
          evidence supports. When the carrier returns a revised BL, all seven
          fields are compared again: fixed fields are confirmed and any new
          regression is shown, round by round.
        </p>

        <h2>What the inbox colours mean</h2>
        <p>
          Every email has one state, shown as words and an icon as well as a
          colour:
        </p>
        <ul>
          <li><strong>Red</strong>: spam, or held because it looks like phishing</li>
          <li><strong>Yellow</strong>: a person has something to do: documents missing, waiting for a draft, needs review, or a mismatch found</li>
          <li><strong>Green</strong>: checked, all seven fields match</li>
          <li><strong>Light green</strong>: classified, and no document check is needed</li>
          <li><strong>Grey</strong>: being read now</li>
        </ul>

        <h2>Safety, spam and drift</h2>
        <p>
          Emails are screened for spam and phishing signals (a sender that does
          not match the reply address, deceptive links, requests for
          credentials) before their documents are processed. A suspected
          phishing email is held until a reviewer releases it with a reason.
          Spam can be moved to Trash and restored within 30 days.
        </p>
        <p>
          Sustained changes in the mix of classifications, checked against
          reviewed labels, raise a drift alert for investigation. A shift in
          the mix alone is not treated as proof that accuracy has fallen.
        </p>
      </div>

      <div style={{ marginTop: 48, display: "flex", gap: 20, flexWrap: "wrap" }}>
        <Link
          href="/demo"
          style={{
            display: "inline-flex",
            alignItems: "center",
            background: "var(--brand-800)",
            color: "white",
            fontWeight: 600,
            fontSize: 15,
            padding: "12px 22px",
            borderRadius: "var(--radius)",
          }}
        >
          Try the demo
        </Link>
        <Link
          href="/pricing"
          style={{
            fontSize: 14,
            fontWeight: 500,
            color: "var(--ink-600)",
            textDecoration: "underline",
            display: "flex",
            alignItems: "center",
          }}
        >
          See pricing
        </Link>
      </div>
    </div>
  );
}
