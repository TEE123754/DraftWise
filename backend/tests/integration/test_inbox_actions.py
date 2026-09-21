from uuid import uuid4
from httpx import ASGITransport,AsyncClient
from psycopg.types.json import Jsonb
from app.api.dependencies import Principal,principal
from app.main import create_app
from app.config import Settings
from app.services.trash_retention import purge_trash
from inbox_support import add_document,add_email
from app.services.references import suggestions
from app.repositories.jobs import claim
from app.workers.handlers import Handlers
from app.workers.runner import execute_job
import hashlib


async def test_trash_alerts_and_tenant_permissions(database,workspace_factory):
    owner=await workspace_factory();other=await workspace_factory()
    app=create_app(Settings(environment="test"));app.state.database=database
    context=Principal(owner["user"],owner["workspace"],"operator")
    app.dependency_overrides[principal]=lambda: context
    async with AsyncClient(transport=ASGITransport(app=app),base_url="http://test") as client:
        eid=str(owner["email"]);reason={"reason":"Reviewed the original message"}
        assert (await client.post("/api/v1/emails/trash",json={**reason,"email_ids":[eid]})).status_code==403
        context=Principal(owner["user"],owner["workspace"],"reviewer")
        assert (await client.request("DELETE",f"/api/v1/emails/{other['email']}",json=reason)).status_code==404
        assert (await client.request("DELETE",f"/api/v1/emails/{eid}",json=reason)).status_code==200
        assert (await client.get("/api/v1/emails")).json()["total"]==0
        assert (await client.get("/api/v1/emails?trash=true")).json()["total"]==1
        assert (await client.get(f"/api/v1/emails/{eid}")).status_code==404
        assert (await client.post(f"/api/v1/emails/{eid}/process",headers={"Idempotency-Key":"trash"},json={"prefer_ai":False})).status_code==404
        assert (await client.post(f"/api/v1/emails/{eid}/restore",json=reason)).status_code==200
        async with database.connection() as conn:
            alert=uuid4()
            await conn.execute("insert into public.drift_alerts(id,workspace_id,alert_type,title,description,sample_email_ids) values(%s,%s,'spam','Review','Signals',%s)",(alert,owner["workspace"],Jsonb([eid])))
        route=f"/api/v1/alerts/{alert}/action"
        assert (await client.post(route,json={"action":"investigate","reason":" "*6})).status_code==422
        assert (await client.post(route,json={**reason,"action":"investigate"})).json()["state"]=="investigated"
        assert (await client.post(route,json={**reason,"action":"confirm_spam"})).json()["state"]=="resolved"
        assert (await client.get("/api/v1/emails?trash=true")).json()["total"]==1
        async with database.connection() as conn:
            assert await purge_trash(conn)==0
            await conn.execute("update public.emails set deleted_at=now()-interval '31 days' where id=%s",(owner["email"],))
            assert await purge_trash(conn)==1
            assert (await (await conn.execute("select count(*) as n from public.emails where id=%s",(other["email"],))).fetchone())["n"]==1
            assert (await (await conn.execute("select count(*) as n from public.audit_logs where workspace_id=%s",(owner["workspace"],))).fetchone())["n"]>=4


async def test_exact_reference_link_requires_confirmation_and_runs_offline(database,workspace_factory):
    owner=await workspace_factory();other=await workspace_factory();files={};ids=[]
    values="Booking ref: BK12345\nShipper: Acme\nConsignee: Buyer\nNotify Party: Buyer\nPort of Loading: Singapore\nPort of Discharge: Port Klang\nContainer Count: 2 x 40HC\nGross Weight: 12000 KG\n"
    async with database.connection() as conn:
        await conn.execute("update public.emails set body='Please compare the documents for Booking ref: BK12345' where id=%s",(owner["email"],))
        source=await add_email(conn,owner["workspace"],"source",category="BL_COMPARISON")
        for role in ("SI","BL"):
            x=await add_document(conn,owner["workspace"],source,role+".txt",role)
            row=await (await conn.execute("select a.* from public.attachments a join public.document_extractions x on x.attachment_id=a.id where x.id=%s",(x,))).fetchone()
            data=(("SHIPPING INSTRUCTIONS" if role=="SI" else "BILL OF LADING")+"\n"+values).encode()
            files[row["storage_key"]]=data;ids.append(row["id"])
            await conn.execute("update public.attachments set sha256=%s where id=%s",(hashlib.sha256(data).hexdigest(),row["id"]))
            await conn.execute("insert into public.source_blocks(id,workspace_id,attachment_id,parser_version,ordinal,text_content,locator,quality) values(%s,%s,%s,'v1',0,'Booking ref: BK12345','{}',1)",(uuid4(),owner["workspace"],row["id"]))
    app=create_app(Settings(environment="test"));app.state.database=database
    context=Principal(owner["user"],owner["workspace"],"reviewer");app.dependency_overrides[principal]=lambda:context
    async with AsyncClient(transport=ASGITransport(app=app),base_url="http://test") as client:
        path=f"/api/v1/emails/{owner['email']}"
        found=(await client.get(path+"/document-actions")).json()
        assert len(found["references"]["suggestions"])==2
        async with database.connection() as conn:
            assert (await (await conn.execute("select count(*) as n from public.attachments where email_id=%s",(owner["email"],))).fetchone())["n"]==0
        for i,attachment in enumerate(ids):
            linked=await client.post(path+"/link-document",headers={"Idempotency-Key":f"link-{i}"},json={"attachment_id":str(attachment),"reason":"Confirmed shipment reference"})
            assert linked.status_code==202,linked.text
        context=Principal(other["user"],other["workspace"],"reviewer")
        assert (await client.get(path+"/document-actions")).status_code==404
    class LocalStorage:
        async def download(self,key):
            return files[key.split("/",3)[3]]
    handlers=Handlers(database,LocalStorage(),Settings(environment="test"),None)
    for _ in range(8):
        async with database.connection() as conn: job=await claim(conn)
        if not job: break
        assert job["payload"].get("prefer_ai") is not True
        await execute_job(database,handlers,uuid4(),job)
    async with database.connection() as conn:
        result=await (await conn.execute("select readiness from public.cases where workspace_id=%s and email_id=%s",(owner["workspace"],owner["email"]))).fetchone()
        assert result["readiness"]=="checked"
        # Purge the entire compared case graph, including copied document evidence.
        await conn.execute("update public.emails set deleted_at=now()-interval '31 days' where id=%s",(owner["email"],))
        assert await purge_trash(conn)==1
        assert (await (await conn.execute("select count(*) as n from public.attachments where email_id=%s",(source,))).fetchone())["n"]==2
