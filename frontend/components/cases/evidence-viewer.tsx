"use client";

import { useEffect, useState } from "react";
import { FileText, X } from "lucide-react";
import type { Comparison, Source, SourceBlock } from "@/lib/api/types";
import { api } from "@/lib/api/client";
import { Button } from "@/components/ui/button";
import { label } from "@/lib/utils";
import { FieldReviewForm } from "./field-review-form";

export function EvidenceViewer({
  comparison,
  sources,
  onClose,
  review,
}: {
  comparison: Comparison;
  sources: Source[];
  onClose: () => void;
  review?: {caseId:string;version:number;onSaved:()=>Promise<void>};
}) {
  const [blocks, setBlocks] = useState<Record<string, SourceBlock[]>>({});
  const [error, setError] = useState("");
  useEffect(() => {
    const controller = new AbortController();
    setError("");
    setBlocks({});
    Promise.all(
      [comparison.si, comparison.bl].map(async (value) => {
        const source = sources.find((item) => item.id === value.extraction_id);
        if (!source) return;
        const result = await api<{ blocks: SourceBlock[] }>(
          `/attachments/${source.attachment_id}/preview`,
          { signal: controller.signal },
        );
        return [source.id, result.blocks] as const;
      }),
    )
      .then((results) =>
        setBlocks(
          Object.fromEntries(results.filter((item) => item !== undefined)),
        ),
      )
      .catch((error) => {
        if (error.name !== "AbortError") setError(error.message);
      });
    return () => controller.abort();
  }, [comparison, sources]);
  return (
    <section
      className="card mt-5 p-5"
      aria-label={`${label(comparison.field)} source evidence`}
      tabIndex={-1}
    >
      <div className="flex items-center justify-between">
        <h2 className="font-semibold capitalize">
          {label(comparison.field)} · Source evidence
        </h2>
        <Button variant="ghost" onClick={onClose} aria-label="Close evidence">
          <X size={18} />
        </Button>
      </div>
      <p className="mt-2 text-sm text-slate-600">{comparison.explanation}</p>
      {error && (
        <p role="alert" className="mt-3 text-sm text-red-800">
          {error}
        </p>
      )}
      <div className="mt-5 grid gap-4 md:grid-cols-2">
        {[
          ["Shipping instructions", comparison.si],
          ["Draft bill of lading", comparison.bl],
        ].map(([title, value]) => {
          const field = value as Comparison["si"];
          const source = sources.find(
            (item) => item.id === field.extraction_id,
          );
          const all = blocks[source?.id || ""];
          const evidence = all?.filter((block) =>
            comparison.evidence_ids.includes(block.id),
          );
          return (
            <div
              key={title as string}
              className="rounded-lg border border-slate-200 bg-slate-50 p-4"
            >
              <p className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-slate-600">
                <FileText size={15} />
                {title as string}
              </p>
              <p className="mt-2 text-xs text-slate-500">
                {source?.original_name || "No source selected"}
              </p>
              <p className="mt-4 whitespace-pre-wrap text-sm font-medium">
                {field.raw || "No supported value found"}
              </p>
              {evidence?.map((block) => (
                <blockquote
                  key={block.id}
                  className="mt-4 rounded-md border border-slate-200 bg-white p-3 text-sm"
                >
                  <p className="whitespace-pre-wrap">{block.text_content}</p>
                  <footer className="mt-2 text-xs text-slate-500">
                    {block.locator.page
                      ? `Page ${block.locator.page}`
                      : block.locator.sheet
                        ? `${block.locator.sheet} · ${block.locator.cell}`
                        : block.locator.line
                          ? `Line ${block.locator.line}`
                          : "Document text"}
                  </footer>
                </blockquote>
              ))}
              {source && !all && !error && (
                <p role="status" className="mt-4 text-xs">
                  Loading original evidence…
                </p>
              )}
              {review && source && all && <FieldReviewForm key={`${source.id}-${comparison.field}`} caseId={review.caseId} version={review.version} extractionId={source.id} field={comparison.field} initialValue={field.raw} blocks={all} onSaved={review.onSaved}/>}
            </div>
          );
        })}
      </div>
    </section>
  );
}
