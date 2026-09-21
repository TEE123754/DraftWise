import type { Round } from "@/lib/api/types";

export function AmendmentTimeline({ rounds }: { rounds: Round[] }) {
  return (
    <section className="card p-5">
      <h2 className="font-semibold">Amendment history</h2>
      {!rounds.length ? (
        <p className="mt-3 text-sm text-slate-500">
          Your first check will start the case history.
        </p>
      ) : (
        <ol className="mt-5 space-y-5">
          {rounds.map((round) => (
            <li key={round.id} className="border-b border-slate-200 pb-4">
              <p className="text-sm font-semibold">
                Draft check · Round {round.round_number}
              </p>
              <p className="mt-1 text-xs text-slate-500">
                {new Date(round.created_at).toLocaleString()}
              </p>
              <p className="mt-2 text-xs text-slate-600">
                {
                  round.summary.fields.filter(
                    (field) => field.current_decision === "match",
                  ).length
                }{" "}
                of 7 fields match
              </p>
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}
