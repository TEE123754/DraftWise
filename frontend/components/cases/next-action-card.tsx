import type { NextAction } from "@/lib/api/types";
import { Button } from "@/components/ui/button";

export function NextActionCard({
  action,
  onAction,
  disabled,
}: {
  action: NextAction;
  onAction: () => void;
  disabled?: boolean;
}) {
  const waiting = action.kind === "wait";
  const checked = action.kind === "view_checks";
  return (
    <section aria-label="Next action" className="next-decision">
      <div className="flex items-start gap-3">
        <div>
          <h2 className="mt-1 font-semibold text-brand-950">{action.title}</h2>
          <p className="mt-1 text-sm text-brand-900">
            {checked
              ? "Matched against the selected shipping instructions."
              : waiting
                ? "You can leave this page. The check will continue."
                : "Keep the original documents and every decision together."}
          </p>
        </div>
      </div>
      {!waiting && !checked && (
        <Button onClick={onAction} disabled={disabled}>
          Continue
        </Button>
      )}
    </section>
  );
}
