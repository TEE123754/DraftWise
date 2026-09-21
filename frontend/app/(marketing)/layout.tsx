import type { Metadata } from "next";
import Link from "next/link";
import { WordMark } from "@/components/brand/wordmark";
import { Button } from "@/components/ui/button";
import "./marketing.css";

export const metadata: Metadata = {
  title: {
    template: "%s | DraftWise",
    default: "DraftWise: Smart Emails. Smoother Logistics.",
  },
};
const links = [
  { href: "/#features", label: "Features" },
  { href: "/#workflow", label: "AI Verification" },
  { href: "/dashboard", label: "Dashboard" },
  { href: "/pricing", label: "Pricing" },
  { href: "/#contact", label: "Contact" },
];
export default function MarketingLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="marketing-v2">
      <a href="#main-content" className="skip-link">
        Skip to content
      </a>
      <header className="mw-header">
        <div className="mw-container mw-nav">
          <Link href="/" aria-label="DraftWise home">
            <WordMark variant="horizontal" size="sm" />
          </Link>
          <nav className="mw-desktop-nav" aria-label="Main navigation">
            {links.map((x) => (
              <Link href={x.href} key={x.href}>
                {x.label}
              </Link>
            ))}
          </nav>
          <div className="mw-nav-actions">
            <Button asChild variant="ghost">
              <Link href="/sign-in">Sign In</Link>
            </Button>
            <Button asChild className="mw-primary">
              <Link href="/demo">Get Started</Link>
            </Button>
          </div>
          <details className="mw-mobile-menu">
            <summary>Menu</summary>
            <nav aria-label="Mobile navigation">
              {links.map((x) => (
                <Link href={x.href} key={x.href}>
                  {x.label}
                </Link>
              ))}
              <Link href="/sign-in">Sign In</Link>
              <Link href="/demo">Get Started</Link>
            </nav>
          </details>
        </div>
      </header>
      <main id="main-content">{children}</main>
      <footer className="mw-footer" id="contact">
        <div className="mw-container mw-footer-grid">
          <div>
            <Link
              href="/"
              aria-label="DraftWise home"
              className="mw-footer-logo"
            >
              <WordMark variant="horizontal" size="sm" />
            </Link>
            <p className="mw-footer-tagline">
              Smart Emails. Smoother Logistics.
            </p>
          </div>
          <nav aria-label="Footer">
            {links.map((x) => (
              <Link key={x.href} href={x.href}>
                {x.label}
              </Link>
            ))}
          </nav>
          <div className="mw-footer-social">
            <Link href="/demo">Explore the sample workspace →</Link>
          </div>
        </div>
        <div className="mw-container mw-footer-bottom">
          <p>© {new Date().getFullYear()} DraftWise. All rights reserved.</p>
          <nav aria-label="Legal">
            <Link href="/privacy">Data privacy</Link>
            <Link href="/terms">Terms &amp; conditions</Link>
          </nav>
        </div>
      </footer>
    </div>
  );
}
