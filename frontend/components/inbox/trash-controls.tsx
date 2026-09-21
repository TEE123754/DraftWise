"use client";
import { useState } from "react";
import { post } from "@/lib/api/client";
import { Button } from "@/components/ui/button";
export function TrashControls({
  ids,
  restore = false,
  onChanged,
}: {
  ids: string[];
  restore?: boolean;
  onChanged?: () => void;
}) {
  const [reason, setReason] = useState(""),
    [busy, setBusy] = useState(false),
    [message, setMessage] = useState("");
  return (
    <details className="mt-3">
      <summary>{restore ? "Restore email" : "Move to Trash"}</summary>
      <p className="text-sm mt-2">
        {restore
          ? "Processing stays paused until you review it."
          : "Removes it from this workspace inbox. Restore within 30 days. Gmail is unchanged."}
      </p>
      <label className="block text-sm mt-2">
        Reason
        <textarea
          className="input mt-1"
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          maxLength={1000}
        />
      </label>
      <Button
        className="mt-2"
        disabled={busy || reason.trim().length < 5 || !ids.length}
        onClick={async () => {
          setBusy(true);
          try {
            if (restore) await post(`/emails/${ids[0]}/restore`, { reason });
            else await post("/emails/trash", { email_ids: ids, reason });
            setMessage(restore ? "Restored" : "Moved to Trash");
            window.dispatchEvent(new Event("draftwise:inbox-changed"));
            onChanged?.();
          } catch (e) {
            setMessage((e as Error).message);
          } finally {
            setBusy(false);
          }
        }}
      >
        {restore ? "Restore" : "Confirm move to Trash"}
      </Button>
      {message && (
        <p role="status" className="mt-2">
          {message}
        </p>
      )}
    </details>
  );
}
