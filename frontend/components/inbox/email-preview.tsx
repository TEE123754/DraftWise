import { TrashControls } from "./trash-controls";
import Link from "next/link";
import type { Email, InboxItem } from "@/lib/api/types";
import { CATEGORY_LABELS, PROCESSABLE_ACTIONS } from "@/lib/inbox";
import { Button, buttonVariants } from "@/components/ui/button";
import {
  DocumentChips,
  hasDocumentChips,
  StateChip,
} from "@/components/inbox/chips";
import { FieldTable } from "@/components/inbox/field-table";
import { ReferenceChips } from "@/components/inbox/reference-chips";
import { cn } from "@/lib/utils";

export type PreviewEmail = Email & {
  extractions?: { attachment_id: string; document_type: string }[];
};

const ROLE_TEXT: Record<string, string> = {
  SI: "Shipping instructions",
  BL: "Draft BL",
  INVOICE: "Invoice",
  PACKING_LIST: "Packing list",
  CERTIFICATE: "Certificate",
  UNKNOWN: "Type not recognised",
};

const PROCESS_LABEL: Record<string, string> = {
  process: "Read the documents (no AI)",
  compare: "Compare the documents (no AI)",
  classify: "Classify with rules (no AI)",
};

const BODY_LIMIT = 700;

type Props = {
  item: InboxItem;
  detail: PreviewEmail | null;
  loading: boolean;
  error: string;
  canAct: boolean;
  busy: boolean;
  notice: string;
  onClose: () => void;
  onProcess: () => void;
};

function Section({
  id,
  title,
  children,
}: {
  id: string;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section
      aria-labelledby={id}
      className="mt-5 border-t border-slate-200 pt-4 first:mt-0 first:border-t-0 first:pt-0"
    >
      <h2 id={id} className="text-sm font-semibold text-slate-900">
        {title}
      </h2>
      <div className="mt-2">{children}</div>
    </section>
  );
}

function Pending({ children }: { children: React.ReactNode }) {
  return (
    <p role="status" className="text-sm text-slate-600">
      {children}
    </p>
  );
}

function fileRole(
  detail: PreviewEmail,
  attachmentId: string,
  state: string,
): string {
  if (state === "quarantined") return "Could not be read";
  const role = detail.extractions?.find(
    (item) => item.attachment_id === attachmentId,
  )?.document_type;
  return role ? (ROLE_TEXT[role] ?? role) : "Not read yet";
}

export function EmailPreview({
  item,
  detail,
  loading,
  error,
  canAct,
  busy,
  notice,
  onClose,
  onProcess,
}: Props) {
  const body = detail?.body ?? item.body_preview;
  const clipped =
    body.length > BODY_LIMIT ? `${body.slice(0, BODY_LIMIT).trimEnd()}…` : body;
  const summary = detail?.classification_summary;
  const category = summary?.category ?? item.category;
  return (
    <aside
      aria-label="Email preview"
      data-testid="email-preview"
      className="card p-5"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex flex-wrap items-center gap-2">
          <span className="font-mono text-sm font-semibold text-slate-700">
            {item.display_id}
          </span>
          <StateChip state={item.state} label={item.state_label} />
        </div>
        <Button
          variant="ghost"
          className="min-h-8 px-2 py-1 text-xs"
          onClick={onClose}
        >
          Close preview
        </Button>
      </div>

      <div className="mt-4">
        <Section id="preview-email" title="Email">
          <p className="text-base font-semibold text-slate-900">
            {item.subject || "Untitled email"}
          </p>
          <p className="mt-0.5 text-xs text-slate-600">From {item.sender}</p>
          <p className="mt-3 max-h-44 overflow-y-auto whitespace-pre-wrap rounded-lg bg-slate-50 p-3 text-xs leading-5 text-slate-800">
            {clipped}
          </p>
          <Link
            href={`/inbox/${item.id}`}
            className="mt-2 inline-block text-xs font-semibold"
          >
            Read the full email
          </Link>
        </Section>

        <Section id="preview-attachments" title="Attachments">
          {hasDocumentChips(item) && (
            <p className="flex flex-wrap items-center gap-1.5">
              <DocumentChips item={item} />
            </p>
          )}
          {!item.documents.count ? (
            <p
              className={cn(
                "text-sm text-slate-600",
                hasDocumentChips(item) && "mt-2",
              )}
            >
              No files came with this email.
            </p>
          ) : detail ? (
            <ul className="mt-2 space-y-1">
              {(detail.attachments ?? []).map((file) => (
                <li
                  key={file.id}
                  className="flex items-center justify-between gap-3 rounded bg-slate-100 px-2 py-1 text-xs text-slate-800"
                >
                  <span className="min-w-0 truncate">{file.original_name}</span>
                  <span className="shrink-0 font-medium">
                    {fileRole(detail, file.id, file.state)}
                  </span>
                </li>
              ))}
            </ul>
          ) : (
            <Pending>Loading the file list…</Pending>
          )}
          {detail?.reference_check && <ReferenceChips check={detail.reference_check} />}
        </Section>

        <Section id="preview-classification" title="Classification">
          {summary ? (
            <>
              <p className="text-sm text-slate-900">
                {category
                  ? (CATEGORY_LABELS[category] ?? category)
                  : "Could not be decided"}
                <span className="text-slate-600">
                  {" "}
                  · decided by {summary.method_label}
                </span>
              </p>
              {summary.reason && (
                <p className="mt-1 text-xs text-slate-700">{summary.reason}</p>
              )}
              {summary.human_reason && (
                <p className="mt-1 text-xs text-slate-700">
                  Reviewer note: {summary.human_reason}
                </p>
              )}
              {summary.fallback_reason && (
                <p className="mt-1 text-xs text-slate-700">
                  Fell back to rules (
                  {summary.fallback_reason.replaceAll("_", " ").toLowerCase()}).
                </p>
              )}
              {summary.evidence.length > 0 && (
                <details className="mt-2 text-xs text-slate-700">
                  <summary className="cursor-pointer font-medium">
                    Evidence from the email
                  </summary>
                  {summary.evidence.map((quote) => (
                    <blockquote
                      key={quote.id}
                      className="mt-1 whitespace-pre-wrap border-l-2 border-brand-300 pl-2"
                    >
                      {quote.text}
                    </blockquote>
                  ))}
                </details>
              )}
            </>
          ) : detail ? (
            <p className="text-sm text-slate-600">Not classified yet.</p>
          ) : (
            <Pending>Loading the classification…</Pending>
          )}
        </Section>

        <Section id="preview-actions" title="Actions">
          {canAct && <TrashControls ids={[item.id]} />}
          <p className="text-sm font-medium text-slate-900">
            {item.action.title}
          </p>
          {item.reasons.length > 0 && (
            <ul className="mt-2 list-disc space-y-0.5 pl-5 text-xs text-slate-700">
              {item.reasons.map((reason) => (
                <li key={reason.code}>{reason.label}</li>
              ))}
            </ul>
          )}
          <div className="mt-3 flex flex-wrap gap-2">
            {PROCESSABLE_ACTIONS.has(item.action.kind) && (
              <Button disabled={!canAct || busy} onClick={onProcess}>
                {busy ? "Working…" : PROCESS_LABEL[item.action.kind]}
              </Button>
            )}
            {item.case && (
              <Link
                href={`/cases/${item.case.id}`}
                className={buttonVariants({ variant: "outline" })}
              >
                Open case
              </Link>
            )}
            <Link
              href={`/inbox/${item.id}`}
              className={buttonVariants({ variant: "outline" })}
            >
              Open email and workflow
            </Link>
          </div>
          {notice && (
            <p role="status" className="mt-2 text-xs text-brand-900">
              {notice}
            </p>
          )}
        </Section>

        <Section id="preview-extracted" title="Extracted info">
          {error && (
            <p
              role="alert"
              className="mb-2 rounded-md bg-red-50 p-2 text-xs text-red-900"
            >
              {error}
            </p>
          )}
          {detail?.field_table ? (
            <FieldTable table={detail.field_table} />
          ) : loading ? (
            <Pending>Loading the extracted values…</Pending>
          ) : (
            !error && (
              <p className="text-sm text-slate-600">
                Nothing has been extracted yet.
              </p>
            )
          )}
        </Section>
      </div>
    </aside>
  );
}
