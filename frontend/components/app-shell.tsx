"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { X } from "lucide-react";
import { useState, useEffect, useRef, type ReactNode } from "react";
import { useAuth } from "@/components/auth-provider";
import { API_ROOT } from "@/lib/api/base";
import { Button, buttonVariants } from "@/components/ui/button";
import { Tooltip } from "@/components/ui/tooltip";
import { WordMark } from "@/components/brand/wordmark";
import { getSupabase } from "@/lib/supabase";
import { cn } from "@/lib/utils";
import { post } from "@/lib/api/client";
import { AuthFrame } from "@/components/auth-frame";

const MARKETING_PATHS = ["/", "/workflow", "/pricing", "/privacy", "/terms"];
const DEMO_STANDALONE = ["/demo", "/sign-in", "/auth"];

// Nav items visible to all workspace users (demo or signed in)
const nav = [
  { href: "/dashboard", label: "Overview", hint: "Counts, and the work that needs you today" },
  { href: "/inbox", label: "Inbox", hint: "Every email and what it needs next" },
  { href: "/cases", label: "Cases", hint: "Comparisons in progress, with their evidence" },
  { href: "/review", label: "Review", hint: "Values that need a person's decision" },
  { href: "/rules", label: "Rules", hint: "Approved name and port equivalences" },
  { href: "/analytics", label: "Analytics", hint: "How accurate the classifier is" },
  { href: "/alerts", label: "Alerts", hint: "Spam, phishing and drift warnings" },
  { href: "/trash", label: "Trash", hint: "Deleted emails, restorable for 30 days" },
];

export function AppShell({ children }: { children: ReactNode }) {
  const path = usePathname();
  const auth = useAuth();
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const [assistantOpen, setAssistantOpen] = useState(false);

  // Marketing pages use their own layout: don't wrap with workspace shell
  if (
    MARKETING_PATHS.includes(path) ||
    DEMO_STANDALONE.some((p) => path === p || path.startsWith(p + "/"))
  ) {
    return <>{children}</>;
  }

  const isWorkspace = auth.demo || Boolean(auth.session && auth.workspace);
  if (
    ![
      "/dashboard",
      "/cases",
      "/inbox",
      "/trash",
      "/review",
      "/rules",
      "/analytics",
      "/alerts",
      "/settings",
      "/completed",
    ].some((p) => path === p || path.startsWith(p + "/"))
  )
    return <>{children}</>;

  if (!auth.ready)
    return (
      <AuthFrame>
        <p role="status">Restoring your workspace…</p>
      </AuthFrame>
    );
  if (!isWorkspace)
    return (
      <AuthFrame>
        <p className="auth-kicker">WELCOME TO DRAFTWISE</p>
        <h1>Open your workspace</h1>
        <p className="auth-description">{auth.error || "Sign in to review your shipping emails and document checks, or explore a sample workspace."}</p>
        <div className="auth-access-actions"><Button asChild className="w-full"><Link href="/sign-in">Sign in</Link></Button><Button asChild variant="secondary" className="w-full"><Link href="/demo">Try the demo</Link></Button></div>
        <p className="auth-legal">The demo uses prepared shipment samples. No account required.</p>
      </AuthFrame>
    );

  return (
    <div
      className="workspace-shell"
      style={{
        minHeight: "100vh",
        display: "grid",
        gridTemplateColumns: "240px minmax(0, 1fr)",
      }}
    >
      <a href="#main-content" className="skip-link">
        Skip to content
      </a>

      {/* ─── Sidebar ─────────────────────────────────────────── */}
      <aside
        className="workspace-sidebar"
        aria-label="Workspace navigation"
        style={{
          borderRight: "1px solid var(--border)",
          background: "white",
          position: "sticky",
          top: 0,
          height: "100vh",
          display: "flex",
          flexDirection: "column",
          padding: "20px 16px",
          overflowY: "auto",
        }}
      >
        {/* Logo */}
        <Link
          href="/dashboard"
          aria-label="DraftWise overview"
          style={{ display: "block" }}
        >
          <WordMark size="md" />
          <span className="workspace-purpose">Shipping document review</span>
        </Link>

        {/* Demo banner */}
        {auth.demo && (
          <div
            style={{
              marginTop: 12,
              padding: "8px 12px",
              background: "var(--brand-50)",
              border: "1px solid var(--brand-100)",
              borderRadius: "var(--radius)",
              fontSize: 12,
              color: "var(--brand-800)",
              fontWeight: 600,
            }}
          >
            Sample workspace
          </div>
        )}

        {/* Navigation */}
        <nav
          aria-label="Workspace"
          style={{
            marginTop: 24,
            display: "flex",
            flexDirection: "column",
            gap: 8,
          }}
        >
          {nav.map(({ href, label, hint }) => {
            const active = path === href || path.startsWith(href + "/");
            return (
              <Tooltip key={href} side="right" name={label} description={hint} className="flex w-full">
                <Link
                  href={href}
                  aria-current={active ? "page" : undefined}
                  className={cn(
                    buttonVariants({ variant: active ? "primary" : "secondary", size: "sm" }),
                    "min-h-10 w-full justify-start text-sm",
                  )}
                >
                  {label}
                </Link>
              </Tooltip>
            );
          })}
        </nav>

        {/* Settings */}
        <div
          style={{
            marginTop: 8,
            borderTop: "1px solid var(--border)",
            paddingTop: 8,
          }}
        >
          <Tooltip side="right" name="Settings" description="Connect or disconnect a mailbox" className="flex w-full">
            <Link
              href="/settings/connections"
              className={cn(buttonVariants({ variant: "secondary", size: "sm" }), "min-h-10 w-full justify-start text-sm")}
            >
              Settings
            </Link>
          </Tooltip>
        </div>

        {/* Spacer */}
        <div style={{ flex: 1 }} />

        {/* Account section */}
        {auth.demo ? (
          <div
            style={{
              fontSize: 13,
              color: "var(--ink-600)",
              borderTop: "1px solid var(--border)",
              paddingTop: 12,
            }}
          >
            <p style={{ fontWeight: 600, color: "var(--ink-700)" }}>
              Demo session
            </p>
            <p style={{ marginTop: 4, fontSize: 12, color: "var(--ink-400)" }}>
              Access expires after 8 hours. Sample records are retained locally.
            </p>
            <Button
              variant="link"
              className="mt-2.5"
              disabled={busy}
              tip={{ name: "End demo", description: "Deletes this sample session and returns to the demo page", side: "right" }}
              onClick={async () => {
                setBusy(true);
                setNotice("");
                try {
                  const response = await fetch(`${API_ROOT}/demo/session`, {
                    method: "DELETE",
                    credentials: "include",
                  });
                  if (!response.ok)
                    throw new Error("Could not end the demo. Please retry.");
                  sessionStorage.removeItem("draftwise-demo-workspace");
                  location.assign("/demo");
                } catch {
                  setNotice("Could not end the demo. Please retry.");
                  setBusy(false);
                }
              }}
            >
              {busy ? "Ending…" : "End demo"}
            </Button>
            {notice && (
              <p
                role="alert"
                style={{
                  marginTop: 6,
                  fontSize: 12,
                  color: "var(--status-red)",
                }}
              >
                {notice}
              </p>
            )}
          </div>
        ) : auth.session ? (
          <div
            style={{
              borderTop: "1px solid var(--border)",
              paddingTop: 12,
              fontSize: 13,
            }}
          >
            {auth.memberships.length > 1 && (
              <select
                id="workspace-selector"
                aria-label="Select workspace"
                value={auth.workspace}
                onChange={(e) => auth.selectWorkspace(e.target.value)}
                style={{
                  width: "100%",
                  padding: "6px 8px",
                  borderRadius: "var(--radius)",
                  border: "1px solid var(--border)",
                  fontSize: 13,
                  marginBottom: 8,
                }}
              >
                {auth.memberships.map((m) => (
                  <option key={m.workspace_id} value={m.workspace_id}>
                    {m.workspaces?.name || "Workspace"}
                  </option>
                ))}
              </select>
            )}
            <p
              style={{
                fontSize: 12,
                color: "var(--ink-400)",
                overflow: "hidden",
                textOverflow: "ellipsis",
                whiteSpace: "nowrap",
              }}
              title={auth.session.user.email}
            >
              {auth.session.user.email}
            </p>
            <Button
              variant="link"
              className="mt-2"
              tip={{ name: "Sign out", description: "Ends your session on this device", side: "right" }}
              onClick={() => getSupabase()?.auth.signOut()}
            >
              Sign out
            </Button>
          </div>
        ) : null}
      </aside>

      {/* ─── Main content ─────────────────────────────────────── */}
      <main
        className="workspace-main"
        id="main-content"
        style={{
          minWidth: 0,
          padding: "32px 40px",
          maxWidth: "100%",
        }}
      >
        {!auth.ready ? (
          <p role="status" style={{ color: "var(--ink-400)" }}>
            Loading your workspace…
          </p>
        ) : !auth.configured && !auth.demo ? (
          <section
            style={{
              maxWidth: 480,
              margin: "60px auto 0",
              padding: 32,
            }}
            className="card"
          >
            <h1 style={{ fontSize: 24, marginTop: 12 }}>
              Workspace not configured
            </h1>
            <p
              style={{
                marginTop: 12,
                fontSize: 14,
                color: "var(--ink-600)",
                lineHeight: 1.6,
              }}
            >
              Authentication has not been set up for this installation. Contact
              your administrator to connect your organisation.
            </p>
          </section>
        ) : !auth.session && !auth.demo ? (
          <div
            style={{ display: "flex", justifyContent: "center", marginTop: 60 }}
          >
            <Link
              href="/sign-in"
              style={{
                fontSize: 15,
                fontWeight: 600,
                color: "white",
                background: "var(--brand-800)",
                padding: "12px 24px",
                borderRadius: "var(--radius)",
              }}
            >
              Sign in to continue
            </Link>
          </div>
        ) : auth.error ? (
          <p role="alert" className="alert-error">
            {auth.error}
          </p>
        ) : !auth.workspace ? (
          <p role="status" style={{ color: "var(--ink-600)", marginTop: 32 }}>
            Your account needs a workspace invitation. Contact your
            administrator.
          </p>
        ) : (
          <div key={auth.workspace}>{children}</div>
        )}
      </main>

      {/* ─── Floating chatbot launcher ─────────────────────────── */}
      <Button
        variant="ghost"
        size="bare"
        onClick={() => setAssistantOpen((v) => !v)}
        aria-label="Open Ask DraftWise assistant"
        aria-expanded={assistantOpen}
        tip={{ name: "Ask DraftWise", description: "Ask about your emails, cases and alerts", className: "contents" }}
        className="assistant-launcher"
      >
        <img
          src="/brand/chatbot.png"
          alt=""
          width={64}
          height={64}
          decoding="async"
        />
        {assistantOpen && (
          <span className="assistant-launcher-close" aria-hidden="true">
            <X size={12} strokeWidth={3} />
          </span>
        )}
      </Button>

      {/* ─── Assistant popup panel ────────────────────────────── */}
      {assistantOpen && (
        <AssistantPanel path={path} onClose={() => setAssistantOpen(false)} />
      )}
    </div>
  );
}

/* ─── Inline assistant panel (full impl in assistant-panel.tsx) ─ */
const UUID = "[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}";

/** What the assistant may know about where the question is asked from: the open email or case. */
export function pageContext(path: string) {
  const email = path.match(new RegExp(`^/inbox/(${UUID})$`, "i"))?.[1];
  const caseId = path.match(new RegExp(`^/cases/(${UUID})$`, "i"))?.[1];
  return { path, ...(email ? { email_id: email } : {}), ...(caseId ? { case_id: caseId } : {}) };
}

type Citation = { caseId?: string; emailId?: string; label?: string };

function AssistantPanel({ path, onClose }: { path: string; onClose: () => void }) {
  const panelRef = useRef<HTMLDivElement>(null);
  const closeRef = useRef(onClose);
  closeRef.current = onClose;
  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null;
    const panel = panelRef.current;
    panel?.querySelector<HTMLElement>("button")?.focus();
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") closeRef.current();
      if (event.key !== "Tab" || !panel) return;
      const elements = Array.from(
        panel.querySelectorAll<HTMLElement>(
          "button:not(:disabled), a[href], input:not(:disabled), textarea:not(:disabled)",
        ),
      );
      const first = elements[0],
        last = elements[elements.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last?.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first?.focus();
      }
    };
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("keydown", onKey);
      previous?.focus();
    };
  }, []);
  const [messages, setMessages] = useState<
    { role: "user" | "assistant"; content: string; citations?: Citation[] }[]
  >([
    {
      role: "assistant",
      content:
        "Hello! I can answer questions about your inbox and cases: what needs attention, which emails are missing documents, and what to do with the one you have open. Answers come from your workspace data and link to the emails and cases they mention.",
    },
  ]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);

  const context = pageContext(path);
  const suggestions = [
    ...(context.email_id ? ["What should I do with this email?"] : []),
    ...(context.case_id ? ["What is the status of this case?"] : []),
    "What needs my attention?",
    "Which emails are missing documents?",
    "Which drafts are waiting for a revision?",
    "Are there any drift alerts?",
  ];

  async function send(text?: string) {
    const query = text ?? input.trim();
    if (!query) return;
    setInput("");
    setMessages((m) => [...m, { role: "user", content: query }]);
    setBusy(true);
    try {
      const data = await post<{
        answer: string;
        citations?: Citation[];
      }>("/chat", { message: query, page: pageContext(path) });
      setMessages((m) => [
        ...m,
        {
          role: "assistant",
          content: data.answer,
          citations: data.citations,
        },
      ]);
    } catch {
      setMessages((m) => [
        ...m,
        {
          role: "assistant",
          content: "I am unavailable right now. Please try again in a moment.",
        },
      ]);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div
      className="assistant-panel"
      ref={panelRef}
      role="dialog"
      aria-modal="true"
      aria-label="Ask DraftWise assistant"
      style={{
        position: "fixed",
        bottom: 96,
        right: 28,
        width: 380,
        maxHeight: 560,
        background: "white",
        border: "1px solid var(--border)",
        borderRadius: 16,
        display: "flex",
        flexDirection: "column",
        zIndex: 59,
        boxShadow: "0 12px 40px rgba(11,42,92,0.22)",
        overflow: "hidden",
        animation: "slideUp 0.18s ease-out",
      }}
    >
      {/* Header */}
      <div
        style={{
          padding: "14px 16px",
          background:
            "linear-gradient(135deg, var(--navy-900) 0%, var(--brand-800) 100%)",
          color: "white",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          gap: 12,
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <img
            src="/brand/chatbot.png"
            alt=""
            width={40}
            height={40}
            style={{
              borderRadius: "50%",
              background: "white",
              boxShadow: "0 0 0 2px rgba(255,255,255,0.85)",
              flexShrink: 0,
            }}
          />
          <div>
            <p style={{ fontWeight: 700, fontSize: 15, lineHeight: 1.25 }}>
              Ask DraftWise
            </p>
            <p
              style={{
                fontSize: 12,
                lineHeight: 1.3,
                marginTop: 2,
                color: "#d9e8fe",
              }}
            >
              Smart emails. Smoother logistics.
            </p>
          </div>
        </div>
        <Button
          variant="ghost"
          size="icon"
          onClick={onClose}
          aria-label="Close assistant"
          tip={{ name: "Close", description: "Closes the assistant (Esc)", side: "bottom" }}
          className="rounded-full bg-white/15 text-white hover:bg-white/25"
        >
          <X size={16} />
        </Button>
      </div>

      {/* Messages */}
      <div
        style={{
          flex: 1,
          overflowY: "auto",
          padding: "16px 20px",
          display: "flex",
          flexDirection: "column",
          gap: 12,
        }}
        aria-live="polite"
        aria-label="Conversation"
      >
        {messages.map((msg, i) => (
          <div
            key={i}
            style={{
              display: "flex",
              flexDirection: "column",
              alignItems: msg.role === "user" ? "flex-end" : "flex-start",
            }}
          >
            <div
              style={{
                display: "flex",
                alignItems: "flex-end",
                gap: 8,
                maxWidth: "92%",
              }}
            >
              {msg.role === "assistant" && (
                <img
                  src="/brand/chatbot.png"
                  alt=""
                  width={28}
                  height={28}
                  style={{ borderRadius: "50%", flexShrink: 0 }}
                />
              )}
              <div
                style={{
                  padding: "10px 14px",
                  borderRadius: 10,
                  fontSize: 14,
                  lineHeight: 1.55,
                  background:
                    msg.role === "user" ? "var(--brand-800)" : "var(--surface)",
                  color: msg.role === "user" ? "white" : "var(--ink-900)",
                  border:
                    msg.role === "assistant"
                      ? "1px solid var(--border)"
                      : "none",
                }}
              >
                {msg.content}
              </div>
            </div>
            {msg.citations && msg.citations.length > 0 && (
              <div
                style={{
                  marginTop: 4,
                  display: "flex",
                  gap: 6,
                  flexWrap: "wrap",
                }}
              >
                {msg.citations.map((cite) => {
                  const href = cite.emailId ? `/inbox/${cite.emailId}` : `/cases/${cite.caseId}`;
                  const text = cite.emailId ? (cite.label ?? "Email") : `Case ${(cite.caseId ?? "").slice(0, 8)}`;
                  return (
                    <Link
                      key={href}
                      href={href}
                      style={{
                        fontSize: 11,
                        color: "var(--brand-800)",
                        background: "var(--brand-50)",
                        padding: "2px 8px",
                        borderRadius: 99,
                        textDecoration: "none",
                      }}
                    >
                      {text}
                    </Link>
                  );
                })}
              </div>
            )}
          </div>
        ))}
        {busy && (
          <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <div
              className="skeleton"
              style={{ width: 8, height: 8, borderRadius: "50%" }}
            />
            <div
              className="skeleton"
              style={{ width: 8, height: 8, borderRadius: "50%" }}
            />
            <div
              className="skeleton"
              style={{ width: 8, height: 8, borderRadius: "50%" }}
            />
          </div>
        )}
      </div>

      {/* Suggestions */}
      {messages.length === 1 && (
        <div style={{ padding: "0 20px 12px" }}>
          <p style={{ fontSize: 12, color: "var(--ink-400)", marginBottom: 8 }}>
            Suggested questions
          </p>
          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            {suggestions.map((s) => (
              <Button
                key={s}
                variant="secondary"
                size="sm"
                onClick={() => send(s)}
                className="h-auto justify-start whitespace-normal py-2 text-left font-normal"
              >
                {s}
              </Button>
            ))}
          </div>
        </div>
      )}

      {/* Input */}
      <div
        style={{
          padding: "12px 20px 20px",
          borderTop: "1px solid var(--border)",
          display: "flex",
          gap: 8,
        }}
      >
        <input
          className="input"
          style={{ flex: 1, minHeight: 40 }}
          placeholder="Ask about cases, fields, alerts…"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && !busy && send()}
          aria-label="Your question"
          disabled={busy}
        />
        <Button
          size="sm"
          onClick={() => send()}
          disabled={busy || !input.trim()}
          aria-label="Send message"
          tip={{ name: "Send", description: "Sends your question to the assistant (Enter)" }}
        >
          Send
        </Button>
      </div>
    </div>
  );
}
