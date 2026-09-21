import { Check, Minus, Paperclip, X } from "lucide-react";
import type { EmailReason, InboxItem, ReviewState } from "@/lib/api/types";
import { STATE_LABELS, STATE_STYLE } from "@/lib/inbox";
import { cn } from "@/lib/utils";

const CHIP = "inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-semibold leading-5";

/** The review state as icon, text and colour together, so it never depends on colour alone. */
export function StateChip({ state, label }: { state: ReviewState; label?: string }) {
  const { icon: Icon, chip } = STATE_STYLE[state];
  return (
    <span data-testid="state-chip" data-state={state} className={cn(CHIP, chip)}>
      <Icon aria-hidden className={cn("size-3.5 shrink-0", state === "processing" && "animate-spin")} />
      {label ?? STATE_LABELS[state]}
    </span>
  );
}

/** Why the email is in its state, in words. `skip` hides reasons another chip already shows. */
export function ReasonChips({ reasons, skip = [] }: { reasons: EmailReason[]; skip?: string[] }) {
  const shown = reasons.filter((reason) => !skip.includes(reason.code));
  if (!shown.length) return null;
  return (
    <>
      {shown.map((reason) => (
        <span
          key={reason.code}
          data-reason={reason.code}
          className="inline-flex items-center rounded-md border border-slate-300 bg-white px-1.5 py-0.5 text-xs text-slate-700"
        >
          {reason.label}
        </span>
      ))}
    </>
  );
}

type DocumentStatus = "found" | "missing" | "unread";

const DOCUMENT_STYLE: Record<DocumentStatus, { icon: typeof Check; text: string; cls: string }> = {
  found: { icon: Check, text: "found", cls: "border-green-300 bg-green-50 text-green-900" },
  missing: { icon: X, text: "missing", cls: "border-yellow-400 bg-yellow-100 text-yellow-900" },
  unread: { icon: Minus, text: "not read yet", cls: "border-slate-300 bg-slate-100 text-slate-700" },
};

/** Only a comparison email needs an SI and a BL; for those, say which of the two has arrived. */
export function hasDocumentChips(item: Pick<InboxItem, "category">): boolean {
  return item.category === "BL_COMPARISON";
}

export function DocumentChips({ item }: { item: InboxItem }) {
  const { documents } = item;
  if (!hasDocumentChips(item)) {
    if (!documents.count) return null;
    return (
      <span className="inline-flex items-center gap-1 text-xs text-slate-600">
        <Paperclip aria-hidden className="size-3.5" />
        {documents.count} attachment{documents.count === 1 ? "" : "s"}
      </span>
    );
  }
  const status = (found: boolean): DocumentStatus =>
    found ? "found" : documents.unread > 0 ? "unread" : "missing";
  return (
    <>
      {(["SI", "BL"] as const).map((role) => {
        const kind = status(role === "SI" ? documents.si : documents.bl);
        const { icon: Icon, text, cls } = DOCUMENT_STYLE[kind];
        return (
          <span
            key={role}
            data-document={role}
            data-status={kind}
            className={cn("inline-flex items-center gap-1 rounded-md border px-1.5 py-0.5 text-xs font-medium", cls)}
          >
            <Icon aria-hidden className="size-3" />
            {role} {text}
          </span>
        );
      })}
    </>
  );
}
