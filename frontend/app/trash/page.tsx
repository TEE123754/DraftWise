"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { api } from "@/lib/api/client";
import { TrashControls } from "@/components/inbox/trash-controls";
import { useAuth } from "@/components/auth-provider";
import { Button } from "@/components/ui/button";
type Row = {
  id: string;
  display_id: string;
  subject: string;
  deleted_reason: string;
  deleted_at: string;
};
export default function Trash() {
  const auth = useAuth();
  const [items, setItems] = useState<Row[]>([]),
    [error, setError] = useState(""),
    [offset, setOffset] = useState(0),
    [total, setTotal] = useState(0),
    [version, setVersion] = useState(0);
  useEffect(() => {
    api<{ items: Row[]; total: number }>(
      `/emails?trash=true&limit=25&offset=${offset}`,
    )
      .then((r) => {
        setItems(r.items);
        setTotal(r.total);
      })
      .catch((e) => setError(e.message));
  }, [offset, version]);
  return (
    <>
      <Link href="/inbox">Back to inbox</Link>
      <h1 className="text-2xl font-semibold mt-4">Trash</h1>
      <p className="mt-2">
        Restore within 30 days. Removing an email here never changes Gmail.
      </p>
      {error && <p role="alert">{error}</p>}
      <ul className="mt-5 space-y-4">
        {items.map((r) => (
          <li key={r.id} className="card p-4">
            <h2 className="font-semibold">
              {r.display_id}: {r.subject}
            </h2>
            <p className="text-sm">{r.deleted_reason}</p>
            <p className="text-sm">
              Removed {new Date(r.deleted_at).toLocaleString()}
            </p>
            {auth.role !== "viewer" && (
              <TrashControls
                ids={[r.id]}
                restore
                onChanged={() => setVersion((v) => v + 1)}
              />
            )}
          </li>
        ))}
      </ul>
      {!items.length && <p className="mt-4">No emails on this page.</p>}
      <div className="flex gap-4 mt-4">
        <Button
          variant="secondary"
          disabled={!offset}
          onClick={() => setOffset((o) => Math.max(0, o - 25))}
        >
          Previous
        </Button>
        <Button
          variant="secondary"
          disabled={offset + 25 >= total}
          onClick={() => setOffset((o) => o + 25)}
        >
          Next
        </Button>
      </div>
    </>
  );
}
