import type { Metadata } from "next";
import Link from "next/link";
import { ArrowRight, Play } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { HeroParallax } from "@/components/marketing/hero-parallax";
import { WorkflowSteps } from "@/components/marketing/workflow-steps";
import { FeatureGrid } from "@/components/marketing/feature-grid";

export const metadata: Metadata = {
  title: { absolute: "DraftWise | AI-Powered Shipping Email Verification" },
  description:
    "Review shipping emails, compare shipping instructions with draft bills of lading, and prepare evidence-backed follow-ups with DraftWise.",
  alternates: { canonical: "/" },
};

export default function Landing() {
  return (
    <>
      {/* ── Hero ─────────────────────────────────────────────── */}
      <section className="mw-hero mw-container" aria-labelledby="hero-title">
        <div className="mw-hero-copy">
          <Badge className="mw-eyebrow">
            <span className="mw-pulse" />
            AI-ASSISTED SHIPPING DOCUMENT REVIEW
          </Badge>
          <h1 id="hero-title">
            Verify Shipping Emails
            <br className="mw-desktop-break" />{" "}
            <span className="mw-hero-highlight">with Clear Next Steps</span>
          </h1>
          <p className="mw-hero-description">
            Compare shipping instructions with draft bills of lading. Find
            missing documents, inspect shipment details, and prepare the right
            follow-up.
          </p>
          <div className="mw-actions">
            <Button asChild className="mw-primary">
              <Link href="/demo">
                Verify Email <ArrowRight size={18} aria-hidden="true" />
              </Link>
            </Button>
            <Button asChild variant="secondary" className="mw-secondary">
              <Link href="/demo">
                <Play size={15} aria-hidden="true" />
                Try Demo
              </Link>
            </Button>
          </div>
        </div>
        <HeroParallax />
      </section>

      {/* ── Workflow & Features ──────────────────────────────── */}
      <div className="mw-container">
        <WorkflowSteps />
        <FeatureGrid />
      </div>

      {/* ── Bottom CTA ───────────────────────────────────────── */}
      <section
        className="mw-container mw-bottom-cta"
        aria-labelledby="cta-title"
      >
        <div>
          <p className="mw-kicker">YOUR NEXT SHIPMENT, WITH MORE CLARITY</p>
          <h2 id="cta-title">See the evidence. Know the next step.</h2>
          <p>
            Open a sample email, inspect its documents, and follow a case
            through review.
          </p>
        </div>
        <Button asChild className="mw-primary">
          <Link href="/demo">
            Explore DraftWise <ArrowRight size={18} aria-hidden="true" />
          </Link>
        </Button>
      </section>
    </>
  );
}
