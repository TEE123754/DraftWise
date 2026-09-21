import { Mail, ScanText, ShieldCheck, Send, ArrowRight } from "lucide-react";
import {
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
} from "@/components/ui/card";
import { MotionSurface } from "./motion-surface";

const steps = [
  {
    title: "Email & Documents",
    text: "Add an email and its attachments, or explore prepared demo shipments.",
    Icon: Mail,
  },
  {
    title: "AI Analysis",
    text: "Classify the request and extract shipping details with source evidence.",
    Icon: ScanText,
  },
  {
    title: "Compare & Review",
    text: "Compare seven SI/B/L fields. Flag mismatches, missing data and uncertainty.",
    Icon: ShieldCheck,
  },
  {
    title: "Prepare a Reply",
    text: "Draft a document request or correction. Review and copy it before sending.",
    Icon: Send,
  },
];
export function WorkflowSteps() {
  return (
    <section
      id="workflow"
      className="mw-workflow mw-section"
      aria-labelledby="workflow-title"
    >
      <div className="mw-section-heading">
        <div>
          <h2 id="workflow-title">AI Verification Workflow</h2>
        </div>
      </div>
      <ol className="mw-four-grid">
        {steps.map(({ title, text, Icon }, i) => (
          <li key={title}>
            <MotionSurface tilt>
              <Card className="mw-step">
                <CardHeader>
                  <div className="mw-step-top">
                    <span className="mw-icon">
                      <Icon size={23} aria-hidden="true" />
                    </span>
                  </div>
                  <CardTitle>{title}</CardTitle>
                  <CardDescription>{text}</CardDescription>
                </CardHeader>
              </Card>
            </MotionSurface>
            {i < 3 && (
              <ArrowRight
                className="mw-connector"
                size={18}
                aria-hidden="true"
              />
            )}
          </li>
        ))}
      </ol>
    </section>
  );
}
