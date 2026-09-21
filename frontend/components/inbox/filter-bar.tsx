import { X } from "lucide-react";
import { Button } from "@/components/ui/button";
import type { InboxCounts, ReviewState } from "@/lib/api/types";
import { CATEGORY_LABELS, STATE_LABELS, STATE_ORDER, STATE_STYLE, type InboxFilters } from "@/lib/inbox";
import { cn } from "@/lib/utils";

type Props = {
  filters: InboxFilters;
  counts: InboxCounts | null;
  searchText: string;
  onSearch: (text: string) => void;
  onChange: (change: Partial<InboxFilters>) => void;
};

const STATE_HINTS: Record<ReviewState, string> = {
  needs_documents: "Comparison requests missing an SI, a BL, or both",
  waiting_for_draft: "Asks for the draft BL to be sent; nothing to compare yet",
  needs_review: "Unclassified, unreadable or uncertain: a person should look",
  mismatch_found: "SI and BL differ in at least one of the seven fields",
  held: "Suspected phishing, held until someone releases it",
  spam: "Spam; confirm and move to Trash, or mark not spam",
  processing: "Being read and compared now",
  checked: "All seven fields match the shipping instructions",
  classified: "Classified; no document check needed",
};
const CATEGORY_ORDER = ["BL_COMPARISON", "SI_REQUEST", "INVOICE_QUERY", "GENERAL", "SPAM", "unclassified"];

function Pill({ selected, tone, hint, onClick, children }: {
  selected: boolean;
  tone?: string;
  hint: { name: string; description: string };
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <Button
      variant="secondary"
      size="sm"
      aria-pressed={selected}
      onClick={onClick}
      tip={hint}
      className={cn("rounded-full", selected ? "border-slate-900 bg-slate-900 text-white hover:bg-slate-800" : tone)}
    >
      {children}
    </Button>
  );
}

/** Status pills carry the same icon and colour as the rows, so they double as the colour legend. */
export function FilterBar({ filters, counts, searchText, onSearch, onChange }: Props) {
  const count = (state: ReviewState) => counts?.by_state[state];
  return (
    <div className="mt-6 space-y-3">
      <div role="group" aria-label="Filter by status" className="flex flex-wrap items-center gap-1.5">
        <Pill selected={filters.state === "all"} hint={{ name: "All emails", description: "Shows every email, whatever its state" }} onClick={() => onChange({ state: "all" })}>
          All{counts && <span data-count="all">{counts.total}</span>}
        </Pill>
        {STATE_ORDER.map((state) => {
          const { icon: Icon, chip } = STATE_STYLE[state];
          return (
            <Pill key={state} selected={filters.state === state} tone={chip} hint={{ name: STATE_LABELS[state], description: STATE_HINTS[state] }} onClick={() => onChange({ state })}>
              <Icon aria-hidden className="size-3.5" />
              {STATE_LABELS[state]}
              {counts && <span data-count={state}>{count(state)}</span>}
            </Pill>
          );
        })}
      </div>
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
        <label className="flex items-center gap-2 text-xs font-semibold text-slate-700">
          Type
          <select
            className="input min-h-9 w-auto min-w-48 py-1 text-xs"
            value={filters.category}
            onChange={(event) => onChange({ category: event.target.value })}
          >
            <option value="all">All types{counts ? ` (${counts.total})` : ""}</option>
            {CATEGORY_ORDER.map((key) => (
              <option key={key} value={key}>
                {CATEGORY_LABELS[key]}
                {counts ? ` (${counts.by_category[key] ?? 0})` : ""}
              </option>
            ))}
          </select>
        </label>
        <input
          type="search"
          aria-label="Search by subject, sender or email ID"
          placeholder="Search subject, sender or ID (e.g. email_007)"
          value={searchText}
          onChange={(event) => onSearch(event.target.value)}
          className="input min-h-9 w-full py-1 text-xs sm:w-80"
        />
        {filters.failed && (
          <Button
            variant="secondary"
            size="sm"
            onClick={() => onChange({ failed: false })}
            tip={{ name: "Failed processing", description: "Only emails whose last processing job failed. Select to show all again" }}
            className="rounded-full border-red-300 bg-red-100 text-red-900"
          >
            <X aria-hidden className="size-3.5" />
            Failed processing only
          </Button>
        )}
      </div>
    </div>
  );
}
