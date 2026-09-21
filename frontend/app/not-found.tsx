import Link from "next/link";
import { WordMark } from "@/components/brand/wordmark";

export default function NotFound() {
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
        textAlign: "center",
      }}
    >
      <Link href="/" aria-label="DraftWise home" style={{ marginBottom: 40 }}>
        <WordMark size="md" variant="full" />
      </Link>

      <p
        style={{
          fontSize: 80,
          fontWeight: 700,
          color: "var(--border)",
          lineHeight: 1,
          fontVariantNumeric: "tabular-nums",
        }}
        aria-hidden="true"
      >
        404
      </p>

      <h1 style={{ fontSize: 24, marginTop: 20, color: "var(--ink-900)" }}>
        Page not found
      </h1>
      <p
        style={{
          marginTop: 12,
          fontSize: 15,
          color: "var(--ink-600)",
          maxWidth: 400,
          lineHeight: 1.6,
        }}
      >
        The page you are looking for does not exist or has been moved.
      </p>

      <div
        style={{
          marginTop: 32,
          display: "flex",
          flexWrap: "wrap",
          justifyContent: "center",
          gap: 14,
        }}
      >
        <Link
          href="/"
          style={{
            padding: "11px 22px",
            background: "var(--brand-800)",
            color: "white",
            borderRadius: "var(--radius)",
            fontWeight: 600,
            fontSize: 14,
            textDecoration: "none",
          }}
        >
          Go to homepage
        </Link>
        <Link
          href="/demo"
          style={{
            padding: "11px 22px",
            border: "1px solid var(--border)",
            background: "white",
            color: "var(--ink-700)",
            borderRadius: "var(--radius)",
            fontWeight: 500,
            fontSize: 14,
            textDecoration: "none",
          }}
        >
          Try the demo
        </Link>
        <Link
          href="/dashboard"
          style={{
            padding: "11px 22px",
            border: "1px solid var(--border)",
            background: "white",
            color: "var(--ink-700)",
            borderRadius: "var(--radius)",
            fontWeight: 500,
            fontSize: 14,
            textDecoration: "none",
          }}
        >
          Open workspace
        </Link>
      </div>
    </div>
  );
}
