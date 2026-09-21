import type { Metadata } from "next";
import Link from "next/link";
import { WordMark } from "@/components/brand/wordmark";

export const metadata: Metadata = {
  title: {
    template: "%s | DraftWise",
    default: "DraftWise: Every draft checked. Every change explained.",
  },
};

export default function MarketingLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <>
      {/* Skip link */}
      <a href="#main-content" className="skip-link">
        Skip to content
      </a>

      {/* Top navigation */}
      <header className="site-header">
        <div className="site-header-inner">
          <Link href="/" aria-label="DraftWise home">
            <WordMark size="sm" />
          </Link>

          <nav aria-label="Main navigation" className="site-nav">
            <Link href="/workflow" className="site-nav-link">
              How it works
            </Link>
            <Link href="/pricing" className="site-nav-link">
              Pricing
            </Link>
            <Link href="/demo" className="site-nav-cta">
              Try demo
            </Link>
          </nav>
        </div>
      </header>

      {/* Page content */}
      <main id="main-content">{children}</main>

      {/* Footer */}
      <footer className="site-footer">
        <div className="site-footer-inner">
          <div className="site-footer-brand">
            <WordMark size="sm" />
            <p className="site-footer-tagline">
              Every draft checked. Every change explained.
            </p>
          </div>
          <nav aria-label="Footer" className="site-footer-nav">
            {[
              { href: "/workflow", label: "How it works" },
              { href: "/pricing", label: "Pricing" },
              { href: "/privacy", label: "Privacy" },
              { href: "/terms", label: "Terms" },
              { href: "/demo", label: "Try demo" },
            ].map(({ href, label }) => (
              <Link key={href} href={href} className="site-footer-link">
                {label}
              </Link>
            ))}
          </nav>
        </div>
        <div className="site-footer-bottom">
          <p>
            &copy; {new Date().getFullYear()} DraftWise. Document comparison
            checks confirm document consistency; they do not authorize cargo
            release.
          </p>
          <p className="site-footer-team">
            Engineered by Team Commitment Issues
          </p>
        </div>
      </footer>
    </>
  );
}
