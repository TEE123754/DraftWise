"use client";

import {
  Files,
  ListChecks,
  MessageSquareText,
  ShieldAlert,
} from "lucide-react";
import {
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardContent,
} from "@/components/ui/card";
import { MotionSurface } from "./motion-surface";

const features = [
  {
    title: "Document Extraction",
    text: "Extract shipping details from emails, shipping instructions and draft bills of lading, with source quotes.",
    detail: "PDF · DOCX · XLSX · TXT",
    Icon: Files,
    iconColor: "#0d63dd",
    iconBg: "#e8f1ff",
  },
  {
    title: "Shipment Validation",
    text: "Compare shipper, consignee, notify party, loading and discharge ports, container count and gross weight.",
    detail: "Seven fields, one comparison",
    Icon: ListChecks,
    iconColor: "#08734e",
    iconBg: "#dcfce7",
  },
  {
    title: "Document Follow-ups",
    text: "Prepare missing-document requests and evidence-backed corrections. Track returned drafts in the case.",
    detail: "You control the next action",
    Icon: MessageSquareText,
    iconColor: "#e44d26",
    iconBg: "#fee2e2",
  },
  {
    title: "Spam & Phishing Review",
    text: "Inspect suspicious email signals and hold high-risk messages for human review before document processing.",
    detail: "Explainable signals · Human review",
    Icon: ShieldAlert,
    iconColor: "#0b2a5c",
    iconBg: "#e6eef8",
  },
];
export function FeatureGrid() {
  return (
    <section
      id="features"
      className="mw-section"
      aria-labelledby="features-title"
    >
      <div className="mw-section-heading">
        <div>
          <h2 id="features-title">Why Choose DraftWise?</h2>
        </div>
      </div>
      <div className="mw-four-grid">
        {features.map(({ title, text, detail, Icon, iconColor, iconBg }) => (
          <MotionSurface tilt key={title}>
            <Card className="mw-feature">
              <CardHeader>
                <span
                  className="mw-icon"
                  style={{ color: iconColor, background: iconBg }}
                >
                  <Icon size={24} aria-hidden="true" />
                </span>
                <CardTitle>{title}</CardTitle>
                <CardDescription>{text}</CardDescription>
              </CardHeader>
              <CardContent>
                <p className="mw-feature-detail">{detail}</p>
              </CardContent>
            </Card>
          </MotionSurface>
        ))}
      </div>
    </section>
  );
}
