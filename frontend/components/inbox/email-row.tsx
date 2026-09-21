import Link from "next/link";
import type { InboxItem } from "@/lib/api/types";
import { CATEGORY_LABELS, METHOD_LABELS, STATE_STYLE } from "@/lib/inbox";
import { Button, buttonVariants } from "@/components/ui/button";
import { Tooltip } from "@/components/ui/tooltip";
import { DocumentChips, hasDocumentChips, ReasonChips, StateChip } from "@/components/inbox/chips";
import { cn } from "@/lib/utils";

type Props = {
  item: InboxItem;
  selected: boolean;
  selecting: boolean;
  checked: boolean;
  onSelect: () => void;
  onCheck: (checked: boolean) => void;
};

export function EmailRow({ item, selected, selecting, checked, onSelect, onCheck }: Props) {
  const category = CATEGORY_LABELS[item.category ?? "unclassified"] ?? item.category;
  const method = item.classified_by ? METHOD_LABELS[item.classified_by] : null;
  return (
    <li
      data-testid="email-row"
      data-email-id={item.id}
      data-display-id={item.display_id}
      data-state={item.state}
      data-tone={item.tone}
      className={cn(
        "flex items-start border-l-4 transition-colors",
        STATE_STYLE[item.state].row,
        selected && "outline-2 -outline-offset-2 outline-brand-700",
      )}
    >
      {selecting && (
        <label className="flex items-center self-stretch pl-3">
          <input
            type="checkbox"
            className="size-4 accent-brand-800"
            checked={checked}
            onChange={(event) => onCheck(event.target.checked)}
          />
          <span className="sr-only">Select {item.display_id}</span>
        </label>
      )}
      <Button
        type="button"
        variant="ghost"
        size="bare"
        onClick={onSelect}
        aria-current={selected || undefined}
        className="min-w-0 flex-1 flex-col items-stretch justify-start gap-0 whitespace-normal rounded-none p-4 text-left font-normal hover:bg-black/5"
      >
        <span className="flex flex-wrap items-center gap-x-2 gap-y-1">
          <span className="font-mono text-xs font-semibold text-slate-700">{item.display_id}</span>
          <StateChip state={item.state} label={item.state_label} />
          <span className="text-xs text-slate-600">
            {category}
            {method && ` · ${method}`}
          </span>
        </span>
        <span className="mt-1 block truncate text-sm font-semibold text-slate-900">
          {item.subject || "Untitled email"}
        </span>
        <span className="mt-0.5 block truncate text-xs text-slate-600">From {item.sender}</span>
        <span className="mt-2 flex flex-wrap items-center gap-1.5">
          <DocumentChips item={item} />
          <ReasonChips
            reasons={item.reasons}
            skip={hasDocumentChips(item) ? ["missing_si", "missing_bl"] : []}
          />
        </span>
        <span className="mt-2 block text-xs text-slate-700">Next: {item.action.title}</span>
      </Button>
      <Tooltip name="Open email" description="Full email with its workflow steps" side="left" className="m-3 shrink-0">
        <Link href={`/inbox/${item.id}`} className={cn(buttonVariants({ variant: "secondary", size: "sm" }))}>
          Open<span className="sr-only"> {item.display_id}</span>
        </Link>
      </Tooltip>
    </li>
  );
}
