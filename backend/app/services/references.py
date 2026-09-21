"""Exact, labelled shipping identifiers. Voyage names and fuzzy matches never link documents."""
import re

from psycopg.types.json import Jsonb

from app.services.classification import segment_email

PATTERNS = {
    "bl": r"\b(?:b/?l|bill\s+of\s+lading)\s*(?:no\.?|number|ref(?:erence)?|#)\s*[:#.-]?\s*([A-Z0-9][A-Z0-9/-]{4,39})",
    "booking": r"\bbooking\s*(?:no\.?|number|ref(?:erence)?|#)\s*[:#.-]?\s*([A-Z0-9][A-Z0-9/-]{4,39})",
    "oc": r"\bOC\s*(?:no\.?|number|ref(?:erence)?|#)?\s*[:#.-]?\s*([A-Z0-9][A-Z0-9/-]{4,39})",
}


# Wider pattern for the advisory "does the email match its own documents" check only: two to five capitals
# then six to twelve digits (SIN525534192). Case-sensitive, so ordinary words never match. It is never used
# to link one email's documents to another: linking stays with the labelled patterns above.
GENERIC = r"(?-i:\b([A-Z]{2,5}\d{6,12})\b)"


def references(text, generic=False):
    found=[]
    if generic:
        found += [{"kind":"code","code":m[1],"quote":m[0]} for m in re.finditer(GENERIC,text)]
    for kind,pattern in PATTERNS.items():
        for match in re.finditer(pattern,text,re.I):
            code=re.sub(r"[^A-Z0-9]","",match[1].upper())
            if any(c.isdigit() for c in code):
                found.append({"kind":kind,"code":code,"quote":match[0]})
    return found


async def suggestions(connection,workspace,email):
    # Cache exact source evidence. An upsert cannot invent a reference not in a source block.
    blocks=await (await connection.execute("""select b.id,b.attachment_id,b.text_content from public.source_blocks b
        join public.attachments a on a.workspace_id=b.workspace_id and a.id=b.attachment_id
        join public.emails e on e.workspace_id=a.workspace_id and e.id=a.email_id
        where b.workspace_id=%s and e.deleted_at is null and a.state='validated'""",(workspace,))).fetchall()
    found=[{"attachment_id":str(b["attachment_id"]),"block_id":str(b["id"]),**r} for b in blocks for r in references(b["text_content"])]
    if found:
        await connection.execute("""insert into public.document_references(workspace_id,attachment_id,kind,code,quote,block_id)
            select %s,x.attachment_id,x.kind,x.code,x.quote,x.block_id from jsonb_to_recordset(%s)
            as x(attachment_id uuid,kind text,code text,quote text,block_id uuid) on conflict do nothing""",(workspace,Jsonb(found)))
    current=references("\n".join(s["text"] for s in segment_email(email["subject"],email["body"]) if s["id"] in {"subject","current"}))
    keys={(r["kind"],r["code"]) for r in current}
    rows=await (await connection.execute("""select r.*,a.email_id,a.original_name,x.document_type,e.external_id from public.document_references r
        join public.attachments a on a.workspace_id=r.workspace_id and a.id=r.attachment_id
        join public.emails e on e.workspace_id=a.workspace_id and e.id=a.email_id
        join lateral(select document_type from public.document_extractions where workspace_id=a.workspace_id and attachment_id=a.id order by revision desc limit 1)x on true
        left join public.email_safety s on s.workspace_id=e.workspace_id and s.email_id=e.id
        where r.workspace_id=%s and e.deleted_at is null and a.state='validated' and not coalesce(s.held_for_review,false)
        and (select category from public.email_classifications where workspace_id=e.workspace_id and email_id=e.id order by revision desc limit 1) is distinct from 'SPAM'
        and x.document_type in ('SI','BL')""",(workspace,))).fetchall()
    matched=[r for r in rows if (r["kind"],r["code"]) in keys]
    own=[r for r in matched if r["email_id"]==email["id"]]
    others=[r for r in matched if r["email_id"]!=email["id"]]
    # A shared identifier can have multiple candidates; show them, never auto-select.
    return {"email_references":current,"status":"matched" if own else "no_match" if keys else "no_reference",
            "own_matches":own,"suggestions":others,"method":"exact_labelled_references"}


def reference_check(cited, own, has_documents):
    """Whether the identifiers an email cites also appear in its own documents. Advisory: it never changes
    the email's state and never links anything. Codes are compared regardless of label ("Booking ref" in the
    email, "B/L no." in the document)."""
    if not has_documents:
        return {"status": "no_documents", "cited": []}
    in_documents = {r["code"] for r in own}
    seen, rows = set(), []
    for item in cited:
        if item["code"] not in seen:
            seen.add(item["code"])
            rows.append({"code": item["code"], "kind": item["kind"], "quote": item["quote"], "in_documents": item["code"] in in_documents})
    if not rows:
        return {"status": "none_cited", "cited": []}
    found = sum(row["in_documents"] for row in rows)
    return {"status": "matches" if found == len(rows) else "partial" if found else "flagged", "cited": rows}


async def check_email(connection, workspace, email_id, subject, body, has_documents):
    """`reference_check` for one stored email, from its current message and its read documents."""
    blocks = await (await connection.execute(
        """select b.text_content from public.source_blocks b join public.attachments a
        on a.workspace_id=b.workspace_id and a.id=b.attachment_id
        where a.workspace_id=%s and a.email_id=%s and a.state='validated'""", (workspace, email_id))).fetchall()
    own = [r for block in blocks for r in references(block["text_content"], generic=True)]
    current = "\n".join(x["text"] for x in segment_email(subject, body) if x["id"] in {"subject", "current"})
    return reference_check(references(current, generic=True), own, has_documents)
