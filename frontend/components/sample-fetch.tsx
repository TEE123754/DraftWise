"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/components/auth-provider";
import { post } from "@/lib/api/client";
import { Button } from "@/components/ui/button";

export function SampleFetch() {
  const auth=useAuth(); const router=useRouter();
  const [busy,setBusy]=useState(false),[error,setError]=useState("");
  const [sample,setSample]=useState("email_001");
  if (!auth.demo) return null;
  async function fetchSample() {
    setBusy(true);setError("");
    try { const result=await post<{email_id:string}>("/demo/gmail/fetch",{email_id:sample,prefer_ai:true});router.push(`/inbox/${result.email_id}`); }
    catch(e) {setError((e as Error).message);setBusy(false);}
  }
  return <section className="card mt-6 p-5" aria-labelledby="sample-fetch-title"><h2 id="sample-fetch-title" className="font-semibold">Try an inbox import</h2><p className="mt-2 text-sm text-slate-600">Simulation using the supplied email bundle. No Google account is connected. Existing messages are reused without duplicates.</p><div className="mt-4 flex flex-wrap items-end gap-3"><label className="text-sm">Sample email ID<input className="input mt-1" value={sample} onChange={e=>setSample(e.target.value)} pattern="email_[0-9]{3,6}" maxLength={12}/></label><Button onClick={fetchSample} disabled={busy || !/^email_\d{3,6}$/.test(sample)} tip={{ name: "Simulate Gmail fetch", description: "Imports one prepared sample email; no Google account is used" }}>{busy?"Fetching sample…":"Simulate Gmail fetch"}</Button></div><p className="mt-2 text-sm text-slate-600">email_001 includes its shipping instructions and draft bill of lading. AI review has a session allowance; rules are used if AI is unavailable.</p>{error && <p role="alert" className="mt-3 text-red-800">{error}</p>}</section>;
}
