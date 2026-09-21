import { Check, Minus, X } from "lucide-react";
import type { ReferenceCheck } from "@/lib/api/types";
import { cn } from "@/lib/utils";

const SUMMARY: Record<ReferenceCheck["status"], string> = {
  no_documents: "",
  none_cited: "The email cites no booking, B/L or OC reference, so there is nothing to check against its documents.",
  matches: "Everything the email cites is in its documents.",
  partial: "Some of what the email cites is not in its documents.",
  flagged: "The email cites references that its documents do not contain. Check that the right documents came with it.",
};

/** The identifiers the email cites, each marked as found in its own documents or not. Advisory: it changes no state. */
export function ReferenceChips({ check }: { check: ReferenceCheck }) {
  if (check.status === "no_documents") return null;
  return (
    <div className="mt-3" data-testid="reference-check" data-status={check.status}>
      <p className="text-xs font-semibold text-slate-800">References in the email</p>
      {check.cited.length > 0 && (
        <p className="mt-1 flex flex-wrap items-center gap-1.5">
          {check.cited.map((item) => {
            const Icon = item.in_documents ? Check : X;
            return (
              <span
                key={item.code}
                data-reference={item.code}
                className={cn(
                  "inline-flex items-center gap-1 rounded-md border px-1.5 py-0.5 text-xs font-medium",
                  item.in_documents ? "border-green-300 bg-green-50 text-green-900" : "border-yellow-400 bg-yellow-100 text-yellow-900",
                )}
              >
                <Icon aria-hidden className="size-3" />
                <span className="font-mono">{item.code}</span>
                {item.in_documents ? "in its documents" : "not in its documents"}
              </span>
            );
          })}
        </p>
      )}
      <p className={cn("mt-1 flex items-center gap-1 text-xs text-slate-700")}>
        {check.status === "none_cited" && <Minus aria-hidden className="size-3 shrink-0" />}
        {SUMMARY[check.status]}
      </p>
    </div>
  );
}
