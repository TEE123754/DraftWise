import { cn } from "@/lib/utils";
import type { Readiness } from "@/lib/api/types";

const statuses: Record<Readiness, [string, string]> = {
  needs_source: ["Needs documents", "bg-slate-100 text-slate-700"],
  checking: ["Checking", "bg-blue-50 text-blue-800"],
  needs_decision: ["Needs your decision", "bg-amber-50 text-amber-900"],
  changes_required: ["Changes required", "bg-orange-50 text-orange-900"],
  awaiting_revision: ["Awaiting revision", "bg-slate-100 text-slate-700"],
  checked: ["Seven fields checked", "bg-brand-50 text-brand-900"],
  failed: ["Check interrupted", "bg-red-50 text-red-800"],
};
export function StatusBadge({ status }: { status: Readiness }) {
  const [text, color] = statuses[status];
  return (
    <span
      className={cn(
        "inline-flex rounded-full px-2.5 py-1 text-xs font-semibold",
        color,
      )}
    >
      {text}
    </span>
  );
}
