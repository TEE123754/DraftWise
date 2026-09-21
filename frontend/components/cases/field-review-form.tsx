"use client";
import { useState } from "react";
import { post } from "@/lib/api/client";
import type { FieldName, SourceBlock } from "@/lib/api/types";
import { Button } from "@/components/ui/button";

export function FieldReviewForm({caseId, version, extractionId, field, initialValue, blocks, onSaved}: {
  caseId:string; version:number; extractionId:string; field:FieldName; initialValue:string|null;
  blocks:SourceBlock[]; onSaved:()=>Promise<void>;
}) {
  const [value,setValue]=useState(initialValue || ""),[reason,setReason]=useState("");
  const [selected,setSelected]=useState<string[]>([]),[missing,setMissing]=useState(false);
  const [busy,setBusy]=useState(false),[error,setError]=useState("");
  async function save(event:React.FormEvent) {
    event.preventDefault();setBusy(true);setError("");
    try {
      await post(`/cases/${caseId}/extractions/${extractionId}/review`,{
        expected_version:version,field,reason,
        value:missing?{state:"missing",raw_value:null,evidence:[]}:{state:"present",raw_value:value,
          evidence:blocks.filter(b=>selected.includes(b.id)).map(b=>({block_id:b.id,quote:b.text_content}))},
      });
      await onSaved();
    } catch(e){setError((e as Error).message);}finally{setBusy(false);}
  }
  return <details className="mt-4"><summary>Review extracted value</summary><form onSubmit={save} className="mt-3 space-y-3">
    <p className="text-sm">Copy the value exactly from the document and select its supporting text. Saving preserves the original revision and reruns comparison.</p>
    <label className="block text-sm"><input type="checkbox" checked={missing} onChange={e=>setMissing(e.target.checked)}/> Mark as missing from this document</label>
    {!missing && <><label className="block text-sm">Reviewed value<textarea className="input mt-1" maxLength={4000} value={value} onChange={e=>setValue(e.target.value)} required/></label>
    <fieldset className="max-h-64 overflow-auto border border-slate-200 p-3"><legend className="text-sm">Supporting source text</legend>{blocks.map(b=><label key={b.id} className="block text-sm whitespace-pre-wrap py-2"><input type="checkbox" checked={selected.includes(b.id)} onChange={e=>setSelected(old=>e.target.checked?[...old,b.id]:old.filter(id=>id!==b.id))}/> {b.text_content}</label>)}</fieldset></>}
    <label className="block text-sm">Reason for this review<textarea className="input mt-1" minLength={5} maxLength={1000} value={reason} onChange={e=>setReason(e.target.value)} required/></label>
    {error && <p role="alert">{error}</p>}<Button disabled={busy||reason.trim().length<5||(!missing&&(!value.trim()||!selected.length))}>{busy?"Saving review…":"Save review and recompare"}</Button>
  </form></details>;
}
