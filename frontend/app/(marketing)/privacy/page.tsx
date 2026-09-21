import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Privacy Policy",
  description:
    "How DraftWise collects, uses and protects your data: including Gmail access, AI processing, and data retention.",
  alternates: {
    canonical: `${process.env.SITE_URL || "http://localhost:3000"}/privacy`,
  },
};

export default function PrivacyPage() {
  return (
    <div style={{ maxWidth: 800, margin: "0 auto", padding: "56px 24px" }}>
      <h1 style={{ fontSize: 36, marginTop: 12 }}>Privacy Policy</h1>
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
        Legal details including operator name, jurisdiction, processor
        identities, and retention periods must be reviewed and confirmed
        before any public deployment.
      </div>

      <div className="prose">
        <h2>Who we are</h2>
        <p>
          DraftWise is a shipping document verification tool developed by
          Team Commitment Issues for the Averis × Monash Hackathon. It compares
          draft Bills of Lading against Shipping Instructions across seven
          critical fields.
        </p>

        <h2>What data we collect</h2>
        <h3>Demo sessions</h3>
        <p>
          When you start a demo session, we create a temporary workspace
          containing a copy of the provided sample dataset. We store a
          short-lived, hashed session cookie. Demo uploads are stored for the
          duration of the session (up to 8 hours) and then deleted. No personal
          account information is required.
        </p>

        <h3>Authenticated accounts</h3>
        <p>
          When you sign in, we store your email address and session information
          via Supabase Auth. We also store workspace memberships and the cases,
          emails, and documents you create.
        </p>

        <h3>Gmail data</h3>
        <p>
          If you choose to connect a Gmail inbox, DraftWise requests the{" "}
          <code>gmail.readonly</code> scope only: we can read messages and
          attachments; we cannot send, delete, or modify your email. You will
          see an explicit consent screen listing the exact permissions before
          authorising. We import only the messages you select within the date
          range and label filter you choose. Gmail data is stored in your
          DraftWise workspace and used solely for document comparison. It is not
          shared with third parties for advertising.
        </p>

        <h2>How we use your data</h2>
        <ul>
          <li>To perform document comparison and generate verification reports</li>
          <li>To classify emails and identify potential safety risks</li>
          <li>
            To send email body and attachment content to an AI provider (Gemini)
            for extraction and comparison
          </li>
          <li>To maintain your case history and amendment timeline</li>
          <li>To detect concept drift in classification patterns</li>
        </ul>

        <h2>AI subprocessors</h2>
        <p>
          Document extraction and comparison may use:
        </p>
        <ul>
          <li>
            <strong>Google Gemini</strong>: operated by Google LLC. Processing
            occurs subject to{" "}
            <a
              href="https://policies.google.com/privacy"
              target="_blank"
              rel="noopener noreferrer"
            >
              Google&apos;s privacy policy
            </a>
            .
          </li>
        </ul>
        <p>
          Email and document content is transmitted to these providers only when
          a comparison job is triggered. We do not send data to AI providers
          for training or advertising purposes.
        </p>

        <h2>Data retention and deletion</h2>
        <p>
          Demo session data is deleted after 8 hours. Authenticated workspace
          data is retained while your account is active. You may request
          deletion of your account and associated data at any time through
          your account settings.
        </p>

        <h2>Cookies</h2>
        <p>
          We use one necessary authentication cookie (HttpOnly, SameSite=Lax)
          to maintain your session. We do not use advertising or analytics
          cookies.
        </p>

        <h2>Your rights</h2>
        <p>
          Depending on your jurisdiction, you may have rights to access,
          correct, export or delete your personal data. Response times and
          available remedies depend on applicable law.
        </p>

        <h2>Changes to this policy</h2>
        <p>
          We will update the effective date and notify active users of material
          changes before they take effect.
        </p>
      </div>
    </div>
  );
}
