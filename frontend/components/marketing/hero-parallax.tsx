"use client";

import Image from "next/image";
import { Mail, Check } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { MotionSurface } from "./motion-surface";

export function HeroParallax() {
  return (
    <MotionSurface className="mw-scene">
      <div className="mw-vessel">
        <Image
          src="/images/shipping-assistant-v3.png"
          alt="DraftWise-style shipping assistant behind a container vessel"
          width={1536}
          height={1024}
          sizes="(max-width: 800px) 100vw, 55vw"
          preload
        />
      </div>
      <Card className="mw-float mw-email-float">
        <CardContent>
          <div className="mw-email-title">
            <span className="mw-icon">
              <Mail size={21} aria-hidden="true" />
            </span>
            <div>
              <strong>Shipping Email</strong>
              <small>SI + draft bill of lading</small>
            </div>
          </div>
          <div className="mw-analysis">
            <span className="mw-pulse" />
            Reviewing documents…<span>Illustration</span>
          </div>
        </CardContent>
      </Card>
      <Card className="mw-float mw-check-float">
        <CardContent>
          <small className="mw-example-label">EXAMPLE REVIEW</small>
          {["Documents linked", "Fields compared", "Evidence ready"].map(
            (label) => (
              <div className="mw-check" key={label}>
                <Check size={16} aria-hidden="true" />
                <span>{label}</span>
              </div>
            ),
          )}
          <Badge className="mw-good">Ready for your review</Badge>
        </CardContent>
      </Card>
      <div className="mw-scene-caption">
        From your inbox to a clearer shipment decision.
      </div>
    </MotionSurface>
  );
}
