export type FieldName =
  | "shipper"
  | "consignee"
  | "notify_party"
  | "port_of_loading"
  | "port_of_discharge"
  | "container_count"
  | "gross_weight_kg";
export type Decision =
  "match" | "mismatch" | "missing" | "partial_match" | "uncertain";
export type Readiness =
  | "needs_source"
  | "checking"
  | "needs_decision"
  | "changes_required"
  | "awaiting_revision"
  | "checked"
  | "failed";
export type Comparison = {
  field: FieldName;
  si: {
    raw: string | null;
    normalized: string | number | null;
    extraction_id: string | null;
  };
  bl: Comparison["si"];
  decision: Decision;
  severity: string;
  confidence: number;
  explanation: string;
  evidence_ids: string[];
};
export type Report = {
  id: string;
  status: "OK" | "MISMATCH" | "NEEDS_REVIEW";
  comparisons: Comparison[];
  complete: boolean;
};
export type NextAction = { kind: string; title: string; fields: FieldName[] };
export type CaseSummary = {
  id: string;
  email_id: string;
  reference: string;
  version: number;
  readiness: Readiness;
  updated_at: string;
  open_issue_count: number;
  next_action: NextAction;
  latest_report_id: string | null;
};
export type Source = {
  id: string;
  attachment_id: string;
  document_type: string;
  original_name: string;
  revision: number;
};
export type Round = {
  id: string;
  round_number: number;
  created_at: string;
  summary: {
    fields: { field: FieldName; change: string; current_decision: Decision }[];
  };
};
export type CaseDetail = {
  current_job?: {
    id: string;
    state: string;
    error_code: string | null;
    attempt: number;
  } | null;
  case: CaseSummary;
  latest_report: Report | null;
  issues: {
    id: string;
    field: FieldName;
    state: string;
    source_report_id: string;
  }[];
  active_sources: {
    si_extraction_id: string | null;
    bl_extraction_id: string | null;
  };
  available_sources: Source[];
  rounds: Round[];
};
export type Preview = {
  id: string;
  case_version: number;
  changes: {
    field: FieldName;
    current: string | number;
    required: string | number;
  }[];
  remaining_fields: FieldName[];
  remaining_blocker_count: number;
  expires_at: string;
  suggested_message: string;
};
export type Job = {
  id: string;
  state: string;
  error_code: string | null;
  result: unknown;
};
export type ReviewState =
  | "spam"
  | "held"
  | "processing"
  | "needs_documents"
  | "waiting_for_draft"
  | "needs_review"
  | "mismatch_found"
  | "checked"
  | "classified";
export type Tone = "red" | "yellow" | "green" | "grey";
export type EmailReason = { code: string; label: string; fields?: string[] };
export type EmailAction = { kind: string; title: string };
export type EmailDocuments = {
  count: number;
  si: boolean;
  bl: boolean;
  other: number;
  unread: number;
};
/** One row of `GET /emails`: the email plus the review state the server derived for it. */
export type InboxItem = {
  id: string;
  /** The email's own ID (email_007), or M-001 for manually added mail. Never a list position. */
  display_id: string;
  external_id: string;
  subject: string;
  sender: string;
  body_preview: string;
  category: string | null;
  classified_by: "rule" | "ai" | "human" | null;
  attachment_count: number;
  documents: EmailDocuments;
  case: { id: string; readiness: string } | null;
  job_state: string | null;
  state: ReviewState;
  state_label: string;
  tone: Tone;
  reasons: EmailReason[];
  action: EmailAction;
};
export type InboxCounts = {
  total: number;
  by_state: Record<ReviewState, number>;
  by_category: Record<string, number>;
};
export type InboxPage = {
  items: InboxItem[];
  total: number;
  next_cursor: string | null;
};
export type TableSide = {
  state: "present" | "missing" | "ambiguous" | "unreadable" | "no_document";
  value: string | null;
  quote: string | null;
};
export type FieldTableRow = {
  field: FieldName;
  label: string;
  /** SI against BL, from the stored report. Null when no report covers the field. */
  decision: Decision | null;
  explanation: string | null;
  si: TableSide;
  bl: TableSide;
  email: TableSide & { mark: "match" | "differs" | "unchecked" };
};
export type FieldTable = {
  status: "OK" | "MISMATCH" | "NEEDS_REVIEW" | null;
  documents: { si: boolean; bl: boolean };
  rows: FieldTableRow[];
};
export type ClassificationSummary = {
  category: string | null;
  ambiguous: boolean;
  method: "rules" | "ai" | "rule_fallback" | "human";
  method_label: string;
  fallback_reason: string | null;
  reason_code: string | null;
  reason: string | null;
  human_reason: string | null;
  evidence: { id: string; text: string }[];
};
export type ReferenceCheck = {
  status: "no_documents" | "none_cited" | "matches" | "partial" | "flagged";
  cited: { code: string; kind: string; quote: string; in_documents: boolean }[];
};
export type Email = {
  id: string;
  external_id: string;
  subject: string;
  category: string | null;
  sender?: string;
  body?: string;
  /** Same as the list row: the email's own ID, never its position in a list. */
  display_id?: string;
  state?: ReviewState;
  state_label?: string;
  tone?: Tone;
  reasons?: EmailReason[];
  action?: EmailAction;
  documents?: EmailDocuments;
  case?: { id: string; readiness: string } | null;
  classification_summary?: ClassificationSummary | null;
  field_table?: FieldTable;
  /** Whether the identifiers the email cites appear in its own documents. Advisory only. */
  reference_check?: ReferenceCheck;
  /** First 300 chars of body, returned by the list API for quick preview */
  body_preview?: string;
  /** Number of attachments, returned by the list API */
  attachment_count?: number;
  body_extraction?: {
    quoted_history_excluded: boolean;
    extraction: { fields: Record<FieldName, {
      raw_value: string | null; state: string; alternatives: string[];
      evidence: { block_id: string; quote: string }[];
    }> };
  };
  attachments?: { id: string; original_name: string; state: string }[];
};
export type SourceBlock = {
  id: string;
  text_content: string;
  locator: Record<string, unknown>;
  quality: number;
};
export type EquivalenceRuleItem = {
  id: string;
  workspace_id: string;
  customer_id: string;
  field: FieldName;
  left_value: string;
  right_value: string;
  version: number;
  state: "proposed" | "approved" | "revoked";
  content_sha256: string;
  evidence: string[];
  proposed_by: string;
  approved_by?: string | null;
  approved_at?: string | null;
  created_at: string;
};

export type MailboxConnectionItem = {
  id: string;
  workspace_id: string;
  email: string;
  state: "active" | "syncing" | "disconnected" | "error";
  messages_imported: number;
  last_sync_at: string | null;
  last_error: string | null;
  created_at: string | null;
};

export type MailboxConnectionsResponse = {
  items: MailboxConnectionItem[];
  available: boolean;
  configured: boolean;
  message: string | null;
  /** True while fetching mail from Gmail is future development: the message says so. */
  future?: boolean;
};
