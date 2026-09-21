"use client";

import { useState } from "react";
import { download } from "@/lib/api/client";
import { Button } from "@/components/ui/button";

/**
 * Downloads the verification results as a CSV a reviewer can open in Excel: one row per flagged
 * field with the SI and BL values, the confidence, the reason and the source quotes. With an
 * `emailId` it covers that email's seven fields; without one, every flagged field in the workspace.
 */
export function ExportCsvButton({
  emailId,
  label = "Export CSV",
  size,
}: {
  emailId?: string;
  label?: string;
  size?: "md" | "sm";
}) {
  const [state, setState] = useState<"idle" | "working" | "done" | string>("idle");
  const working = state === "working";

  async function run() {
    setState("working");
    const query = emailId ? `?email_id=${emailId}&include_matches=true` : "";
    const name = emailId ? "draftwise-discrepancies-email.csv" : "draftwise-discrepancies.csv";
    try {
      await download(`/exports/discrepancies.csv${query}`, name);
      setState("done");
    } catch (error) {
      setState((error as Error).message);
    }
  }

  const failed = state !== "idle" && state !== "working" && state !== "done";
  return (
    <span className="inline-flex flex-col items-start gap-1">
      <Button variant="outline" size={size} disabled={working} onClick={() => void run()}>
        {working ? "Preparing…" : label}
      </Button>
      {state === "done" && (
        <span role="status" className="text-xs text-slate-600">
          Downloaded. Open it in Excel.
        </span>
      )}
      {failed && (
        <span role="alert" className="text-xs text-red-800">
          {state}
        </span>
      )}
    </span>
  );
}
