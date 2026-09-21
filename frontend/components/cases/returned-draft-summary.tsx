import type { Round } from "@/lib/api/types";
import { label } from "@/lib/utils";

export function ReturnedDraftSummary({ round }: { round: Round }) {
  const fixed = round.summary.fields.filter(
    (field) => field.change === "fixed",
  );
  const regressed = round.summary.fields.filter(
    (field) => field.change === "regressed",
  );
  const unresolved = round.summary.fields.filter(
    (field) => field.change === "unresolved",
  );
  return (
    <section className="card p-5" aria-label="Returned draft summary">
      <p className="text-sm text-slate-600">Revision check {round.round_number}</p>
      <h2 className="mt-2 text-lg font-semibold">What changed in this draft</h2>
      <div className="mt-4 grid gap-4 sm:grid-cols-3">
        {[
          ["Fixed", fixed, "text-brand-800"],
          ["New regressions", regressed, "text-red-800"],
          ["Still uncertain", unresolved, "text-amber-900"],
        ].map(([title, fields, color]) => (
          <div key={title as string}>
            <p className={`text-2xl font-semibold ${color}`}>
              {(fields as typeof fixed).length}
            </p>
            <p className="mt-1 text-sm font-medium">{title as string}</p>
            <p className="mt-1 text-xs capitalize text-slate-500">
              {(fields as typeof fixed)
                .map((field) => label(field.field))
                .join(", ") || "None"}
            </p>
          </div>
        ))}
      </div>
    </section>
  );
}
