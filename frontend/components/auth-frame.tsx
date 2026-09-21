import type { ReactNode } from "react";
import Link from "next/link";
import { WordMark } from "@/components/brand/wordmark";

/** Shared presentation only; authentication remains in its existing handlers. */
export function AuthFrame({ children }: { children: ReactNode }) {
  return (
    <main className="auth-page" id="main-content">
      <header className="auth-header">
        <Link href="/" aria-label="DraftWise home">
          <WordMark size="sm" />
        </Link>
        <Link href="/">Back to website</Link>
      </header>
      <div className="auth-layout">
        <section className="auth-story" aria-labelledby="auth-story-title">
          <p className="auth-kicker">YOUR SHIPPING REVIEW WORKSPACE</p>
          <h2 id="auth-story-title">
            Every draft checked.
            <br />
            Every change explained.
          </h2>
          <p>
            Bring shipping emails, document evidence and the next decision
            together.
          </p>
          <ol className="auth-steps">
            <li>
              <span>01</span>
              <div>
                <strong>Start with the email</strong>
                <p>Keep the shipment request and its documents together.</p>
              </div>
            </li>
            <li>
              <span>02</span>
              <div>
                <strong>Compare the evidence</strong>
                <p>
                  Check seven fields across shipping instructions and the draft
                  bill of lading.
                </p>
              </div>
            </li>
            <li>
              <span>03</span>
              <div>
                <strong>Take the next step</strong>
                <p>
                  Review differences, request missing documents and track
                  returned drafts.
                </p>
              </div>
            </li>
          </ol>
        </section>
        <section className="auth-card" aria-label="Workspace access">
          {children}
        </section>
      </div>
      <footer className="auth-footer">
        <span>Smart Emails. Smoother Logistics.</span>
        <nav aria-label="Legal">
          <Link href="/privacy">Privacy</Link>
          <Link href="/terms">Terms</Link>
        </nav>
      </footer>
    </main>
  );
}
