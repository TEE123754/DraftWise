"use client";

import { useState } from "react";
import { getSupabase } from "@/lib/supabase";
import { Button } from "@/components/ui/button";

export default function SignInForm() {
  const [email, setEmail] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const [sent, setSent] = useState(false);

  async function signIn(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setNotice("");
    try {
      const result = await getSupabase()!.auth.signInWithOtp({
        email,
        options: {
          emailRedirectTo: `${location.origin}/dashboard`,
        },
      });
      if (result.error) {
        setNotice(result.error.message);
      } else {
        setSent(true);
      }
    } catch {
      setNotice("Sign-in could not be started. Please try again.");
    } finally {
      setBusy(false);
    }
  }

  if (sent) {
    return (
      <div
        style={{
          padding: "16px",
          background: "var(--brand-50)",
          border: "1px solid var(--brand-100)",
          borderRadius: "var(--radius)",
          fontSize: 14,
          color: "var(--brand-800)",
          lineHeight: 1.6,
        }}
        role="status"
      >
        <strong>Check your email.</strong> We sent a sign-in link to{" "}
        <strong>{email}</strong>. Use the link to return to your workspace.
      </div>
    );
  }

  return (
    <form
      onSubmit={signIn}
      style={{ display: "flex", flexDirection: "column", gap: 16 }}
    >
      <div>
        <label
          htmlFor="signin-email"
          style={{
            display: "block",
            fontSize: 14,
            fontWeight: 500,
            marginBottom: 6,
          }}
        >
          Work email
        </label>
        <input
          id="signin-email"
          type="email"
          required
          autoComplete="email"
          autoFocus
          className="input"
          placeholder="you@company.com"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
        />
      </div>

      {notice && (
        <p role="alert" style={{ fontSize: 13, color: "var(--status-red)" }}>
          {notice}
        </p>
      )}

      <Button type="submit" disabled={busy} className="w-full">
        {busy ? "Sending link…" : "Email me a sign-in link"}
      </Button>
    </form>
  );
}
