import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Terms of Service",
  description:
    "DraftWise terms of service: acceptable use, service limitations, and account responsibilities.",
  alternates: {
    canonical: `${process.env.SITE_URL || "http://localhost:3000"}/terms`,
  },
};

export default function TermsPage() {
  return (
    <div style={{ maxWidth: 800, margin: "0 auto", padding: "56px 24px" }}>
      <h1 style={{ fontSize: 36, marginTop: 12 }}>Terms of Service</h1>
      <p
        style={{
          marginTop: 8,
          fontSize: 13,
          color: "var(--ink-400)",
          marginBottom: 32,
        }}
      >
        Draft template — this page has not been reviewed by a qualified legal
        professional.
      </p>

      <div
        style={{
          padding: "14px 18px",
          background: "#fef9c3",
          borderRadius: "var(--radius)",
          border: "1px solid #fde047",
          fontSize: 13,
          color: "#713f12",
          marginBottom: 32,
        }}
      >
        This is a draft template prepared for the Averis × Monash Hackathon.
        Operator identity, jurisdiction, and liability limits must be reviewed
        before any public deployment.
      </div>

      <div className="prose">
        <h2>1. Service description</h2>
        <p>
          DraftWise is a document comparison tool that compares Shipping
          Instructions against draft Bills of Lading and highlights
          discrepancies with source evidence. It is developed by Team
          Commitment Issues for the Averis × Monash Hackathon.
        </p>

        <h2>2. Service limitations</h2>
        <p>
          DraftWise performs automated document comparison. Results are provided
          for review purposes only:
        </p>
        <ul>
          <li>
            A verified match does not constitute legal authorization of any
            shipment or document.
          </li>
          <li>
            Extraction accuracy depends on document quality, format, and
            language. Scanned, handwritten, or non-standard documents may
            produce incomplete results.
          </li>
          <li>
            Classification results are probabilistic. Uncertain classifications
            are routed to human review.
          </li>
          <li>
            DraftWise does not read, modify, or send Gmail messages on your
            behalf beyond the{" "}
            <code>gmail.readonly</code> scope you explicitly grant.
          </li>
        </ul>

        <h2>3. Acceptable use</h2>
        <p>You agree not to:</p>
        <ul>
          <li>
            Use DraftWise to process documents you do not have the right to
            share with a cloud service
          </li>
          <li>
            Attempt to access another user&apos;s workspace, session, or documents
          </li>
          <li>Upload malicious files or attempt to exploit the service</li>
          <li>
            Represent DraftWise&apos;s automated outputs as a certified legal opinion
          </li>
          <li>
            Use the service in any way that violates applicable law or
            regulation
          </li>
        </ul>

        <h2>4. Account responsibilities</h2>
        <p>
          You are responsible for maintaining the security of your account
          credentials and for all activity under your account. You must notify
          us promptly if you suspect unauthorized access.
        </p>

        <h2>5. Data and privacy</h2>
        <p>
          Our collection and use of data is described in the{" "}
          <a href="/privacy">Privacy Policy</a>. By using DraftWise you agree to
          its terms.
        </p>

        <h2>6. Disclaimer of warranties</h2>
        <p>
          DraftWise is provided &ldquo;as is&rdquo; without warranty of any kind, express or
          implied. We do not warrant that the service will be error-free,
          uninterrupted, or fit for any particular purpose.
        </p>

        <h2>7. Limitation of liability</h2>
        <p>
          To the maximum extent permitted by applicable law, the developers of
          DraftWise are not liable for any indirect, incidental, special,
          consequential, or punitive damages arising from use of or inability
          to use DraftWise.
        </p>

        <h2>8. Changes to these terms</h2>
        <p>
          We may update these terms. We will notify active users of material
          changes at least 14 days before they take effect. Continued use
          constitutes acceptance.
        </p>
      </div>
    </div>
  );
}
