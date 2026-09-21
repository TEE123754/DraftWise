import type { Metadata } from "next";
import { CaseQueue } from "@/components/cases/case-queue";
import type { Readiness } from "@/lib/api/types";
export const metadata: Metadata = { title: "Cases", description: "Find shipping cases and review their progress.", robots: { index: false } };
const states = ["needs_source", "checking", "needs_decision", "changes_required", "awaiting_revision", "checked", "failed"];
export default async function CasesPage({ searchParams }: { searchParams: Promise<{ readiness?: string; search?: string; open?: string }> }) {
  const params = await searchParams;
  const filter = states.includes(params.readiness || "") ? params.readiness as Readiness : "";
  return <CaseQueue key={`${filter}:${params.search || ""}:${params.open}`} initialFilter={filter} initialSearch={params.search || ""} openOnly={params.open === "true"} />;
}
