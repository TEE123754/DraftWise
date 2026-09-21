import {
  Ban,
  Check,
  CircleAlert,
  CircleCheck,
  FileQuestion,
  GitCompareArrows,
  Hourglass,
  Loader2,
  ShieldAlert,
  type LucideIcon,
} from "lucide-react";
import type { ReviewState } from "@/lib/api/types";

/** Left to right in the filter bar: what needs a person first, what is finished last. */
export const STATE_ORDER: ReviewState[] = [
  "needs_documents",
  "waiting_for_draft",
  "needs_review",
  "mismatch_found",
  "held",
  "spam",
  "processing",
  "checked",
  "classified",
];

export const STATE_LABELS: Record<ReviewState, string> = {
  needs_documents: "Needs documents",
  waiting_for_draft: "Waiting for draft",
  needs_review: "Needs review",
  mismatch_found: "Mismatch found",
  held: "Held for safety",
  spam: "Spam",
  processing: "Processing",
  checked: "Checked",
  classified: "Classified",
};

/**
 * Colour is never the only signal: every state also has an icon and a text label.
 * Red = spam or held, yellow = a person has something to do, green = checked, light green =
 * classified and nothing to check, grey = still being read.
 */
type StateStyle = { icon: LucideIcon; row: string; chip: string };
const RED = "border-red-300 bg-red-100 text-red-900";
const YELLOW = "border-yellow-400 bg-yellow-100 text-yellow-900";
export const STATE_STYLE: Record<ReviewState, StateStyle> = {
  spam: { icon: Ban, row: "border-l-red-600 bg-red-50/70", chip: RED },
  held: { icon: ShieldAlert, row: "border-l-red-600 bg-red-50/70", chip: RED },
  needs_documents: { icon: FileQuestion, row: "border-l-yellow-500 bg-yellow-50/80", chip: YELLOW },
  waiting_for_draft: { icon: Hourglass, row: "border-l-yellow-500 bg-yellow-50/80", chip: YELLOW },
  needs_review: { icon: CircleAlert, row: "border-l-yellow-500 bg-yellow-50/80", chip: YELLOW },
  mismatch_found: { icon: GitCompareArrows, row: "border-l-yellow-500 bg-yellow-50/80", chip: YELLOW },
  checked: {
    icon: CircleCheck,
    row: "border-l-green-600 bg-green-50/80",
    chip: "border-green-400 bg-green-100 text-green-900",
  },
  classified: {
    icon: Check,
    row: "border-l-green-300 bg-green-50/40",
    chip: "border-green-200 bg-green-50 text-green-800",
  },
  processing: {
    icon: Loader2,
    row: "border-l-slate-400 bg-slate-50",
    chip: "border-slate-300 bg-slate-100 text-slate-800",
  },
};

export const CATEGORY_LABELS: Record<string, string> = {
  BL_COMPARISON: "BL comparison",
  SI_REQUEST: "SI request",
  INVOICE_QUERY: "Invoice query",
  GENERAL: "General",
  SPAM: "Spam",
  unclassified: "Unclassified",
};

export const METHOD_LABELS: Record<string, string> = {
  rule: "Rules",
  ai: "AI",
  human: "Reviewer",
};

/** Actions the inbox can run itself, locally and without AI. */
export const PROCESSABLE_ACTIONS = new Set(["process", "compare", "classify"]);

export type InboxFilters = { state: string; category: string; q: string };

/** Query string for `GET /emails`. The same filters are used for every page of one list. */
export function listQuery(filters: InboxFilters): URLSearchParams {
  const query = new URLSearchParams();
  if (filters.state !== "all") query.set("state", filters.state);
  if (filters.category === "unclassified") query.set("unresolved", "true");
  else if (filters.category !== "all") query.set("category", filters.category);
  if (filters.q) query.set("q", filters.q);
  return query;
}

const CATEGORIES = new Set(Object.keys(CATEGORY_LABELS));

/** Filters from a link such as /inbox?state=held. Older links (?unresolved=true, ?safety=true) still work. */
export function filtersFromUrl(params: URLSearchParams): InboxFilters {
  const wanted = params.get("state") ?? (params.get("safety") === "true" ? "held" : "all");
  const category = params.get("category") ?? (params.get("unresolved") === "true" ? "unclassified" : "all");
  return {
    state: (STATE_ORDER as string[]).includes(wanted) ? wanted : "all",
    category: CATEGORIES.has(category) ? category : "all",
    q: (params.get("q") ?? "").slice(0, 200),
  };
}

/** The address that shows these filters, so a refresh or a shared link opens the same view. */
export function urlFor(filters: InboxFilters): string {
  const params = new URLSearchParams();
  if (filters.state !== "all") params.set("state", filters.state);
  if (filters.category !== "all") params.set("category", filters.category);
  if (filters.q) params.set("q", filters.q);
  const query = params.toString();
  return query ? `/inbox?${query}` : "/inbox";
}
