import { Check, CircleAlert, Minus, X, type LucideIcon } from "lucide-react";
import type { Decision, FieldTable as FieldTableData, TableSide } from "@/lib/api/types";
import { cn } from "@/lib/utils";

const GOOD = "border-green-300 bg-green-50 text-green-900";
const WARN = "border-yellow-400 bg-yellow-100 text-yellow-900";
const NEUTRAL = "border-slate-300 bg-slate-100 text-slate-700";

const DECISIONS: Record<Decision, { icon: LucideIcon; text: string; cls: string }> = {
  match: { icon: Check, text: "Match", cls: GOOD },
  mismatch: { icon: X, text: "Mismatch", cls: WARN },
  partial_match: { icon: CircleAlert, text: "Similar, confirm", cls: WARN },
  missing: { icon: Minus, text: "Missing", cls: WARN },
  uncertain: { icon: CircleAlert, text: "Needs check", cls: WARN },
};

function Mark({ icon: Icon, text, cls }: { icon: LucideIcon; text: string; cls: string }) {
  return (
    <span className={cn("inline-flex items-center gap-1 rounded-md border px-1.5 py-0.5 text-xs font-medium", cls)}>
      <Icon aria-hidden className="size-3" />
      {text}
    </span>
  );
}

function Source({ quote }: { quote: string | null }) {
  if (!quote) return null;
  return (
    <details className="mt-1 text-xs text-slate-600">
      <summary className="cursor-pointer">Source</summary>
      <blockquote className="mt-1 whitespace-pre-wrap border-l-2 border-brand-300 pl-2">{quote}</blockquote>
    </details>
  );
}

const ABSENT: Record<TableSide["state"], string> = {
  no_document: "No document",
  missing: "Not found",
  unreadable: "Unreadable",
  ambiguous: "Conflicting values",
  present: "",
};

function Side({ side, absent }: { side: TableSide; absent?: string }) {
  if (side.state === "present" || (side.state === "ambiguous" && side.value)) {
    return (
      <>
        {side.state === "ambiguous" && <span className="block text-slate-600">Conflicting values:</span>}
        <span className="break-words font-medium text-slate-900">{side.value}</span>
        <Source quote={side.quote} />
      </>
    );
  }
  return <span className="italic text-slate-600">{absent ?? ABSENT[side.state]}</span>;
}

export function FieldTable({ table }: { table: FieldTableData }) {
  const { documents, status } = table;
  // With neither document there is nothing to compare, so list only what the email itself states.
  const noDocuments = !documents.si && !documents.bl;
  const rows = noDocuments ? table.rows.filter((row) => row.email.state === "present") : table.rows;
  if (noDocuments && !rows.length) {
    return <p className="text-sm text-slate-600">No SI or BL has been read for this email, and the email states none of the seven fields.</p>;
  }
  const matches = rows.filter((row) => row.decision === "match").length;
  const differences = rows.filter((row) => row.decision === "mismatch").map((row) => row.label.toLowerCase());
  return (
    <>
      <p className="text-sm text-slate-700" data-testid="table-summary">
        {noDocuments
          ? "No SI or BL has been read for this email. These are the values the email states itself."
          : status === null
            ? "Not compared yet."
            : `${matches} of ${rows.length} fields match.${differences.length ? ` Differences: ${differences.join(", ")}.` : ""}`}
      </p>
      <div className="mt-2 overflow-x-auto">
        <table className="w-full min-w-[32rem] border-collapse text-xs" data-testid="field-table">
          <caption className="sr-only">Values for the seven checked fields from the SI, the BL and the email</caption>
          <thead>
            <tr className="border-b border-slate-300 text-left text-slate-700">
              <th scope="col" className="w-[22%] py-1.5 pr-2 font-semibold">Field</th>
              <th scope="col" className="w-[26%] px-2 py-1.5 font-semibold">SI</th>
              <th scope="col" className="w-[26%] px-2 py-1.5 font-semibold">BL</th>
              <th scope="col" className="w-[26%] px-2 py-1.5 font-semibold">Email</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.field} data-field={row.field} data-decision={row.decision ?? "none"} className="border-b border-slate-200 align-top">
                <th scope="row" className="py-2 pr-2 text-left font-semibold text-slate-800">
                  {row.label}
                  <span className="mt-1 block font-normal">
                    <Mark
                      {...(row.decision ? DECISIONS[row.decision] : { icon: Minus, text: "Not compared", cls: NEUTRAL })}
                    />
                  </span>
                  {row.explanation && row.decision !== "missing" && (
                    <span className="mt-1 block font-normal text-slate-600">{row.explanation}</span>
                  )}
                </th>
                <td className="px-2 py-2"><Side side={row.si} /></td>
                <td className="px-2 py-2"><Side side={row.bl} /></td>
                <td className="px-2 py-2">
                  <Side side={row.email} absent="Not stated" />
                  {row.email.state === "present" && (
                    <span className="mt-1 block">
                      {row.email.mark === "match" && <Mark icon={Check} text="Matches the documents" cls={GOOD} />}
                      {row.email.mark === "differs" && <Mark icon={X} text="Differs from the documents" cls={WARN} />}
                      {row.email.mark === "unchecked" && <Mark icon={Minus} text="Not checked" cls={NEUTRAL} />}
                    </span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
