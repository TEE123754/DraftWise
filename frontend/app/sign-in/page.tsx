import type { Metadata } from "next";
import Link from "next/link";
import { WordMark } from "@/components/brand/wordmark";
import SignInForm from "./sign-in-form";

export const metadata: Metadata = {
  title: "Sign in",
  description: "Sign in to your DraftWise workspace.",
  robots: { index: false, follow: false },
};

export default function SignInPage() {
  return (
    <div
      style={{
        minHeight: "100vh",
        background: "var(--surface)",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        padding: 24,
      }}
    >
      <Link href="/" style={{ marginBottom: 40 }} aria-label="DraftWise home">
        <WordMark size="md" variant="full" />
      </Link>

      <div
        className="card"
        style={{ width: "100%", maxWidth: 400, padding: "36px 32px" }}
      >
        <h1 style={{ fontSize: 22, marginBottom: 6 }}>Sign in</h1>
        <p
          style={{ fontSize: 14, color: "var(--ink-600)", marginBottom: 28 }}
        >
          Enter your work email and we will send you a sign-in link.
        </p>

        <SignInForm />

        <div
          style={{
            marginTop: 24,
            paddingTop: 20,
            borderTop: "1px solid var(--border)",
          }}
        >
          <Link
            href="/demo"
            style={{
              display: "block",
              textAlign: "center",
              fontSize: 14,
              fontWeight: 500,
              color: "var(--brand-800)",
            }}
          >
            Try the demo without signing in
          </Link>
        </div>
      </div>

      <p
        style={{
          marginTop: 24,
          fontSize: 12,
          color: "var(--ink-400)",
          textAlign: "center",
          maxWidth: 340,
        }}
      >
        By signing in you agree to our{" "}
        <Link href="/terms" style={{ color: "var(--ink-600)" }}>
          Terms
        </Link>{" "}
        and{" "}
        <Link href="/privacy" style={{ color: "var(--ink-600)" }}>
          Privacy Policy
        </Link>
        .
      </p>
    </div>
  );
}


