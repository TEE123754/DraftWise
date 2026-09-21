from uuid import UUID

from fastapi import APIRouter, Request
from pydantic import Field

from app.ai.provider import create_provider
from app.api.dashboard import workspace_summary
from app.api.dependencies import Viewer
from app.domain.errors import DomainError
from app.domain.models import StrictModel
from app.repositories.emails import load_inbox
from app.services.bounded_ai import BoundedAI
from app.services.email_state import ATTENTION_ORDER

router = APIRouter(tags=["chat"])


class PageContext(StrictModel):
    """Where the user is asking from, so "this email" means something. IDs are checked against the workspace."""

    path: str = Field(default="", max_length=200)
    email_id: UUID | None = None
    case_id: UUID | None = None


class ChatMessage(StrictModel):
    message: str = Field(min_length=1, max_length=2000)
    page: PageContext | None = None


THIS_WORDS = (
    "this email", "this one", "this case", "this message", "this draft", "here", "what should i do",
    "what do i do", "next step", "why is this", "what's wrong", "whats wrong", "what is wrong",
    "explain this", "what happened",
)


def page_intent(question, page):
    """Rules that use the open page or the inbox itself. They cost nothing and never call AI."""
    if page is not None and any(word in question for word in THIS_WORDS):
        if page.email_id:
            return "this_email"
        if page.case_id:
            return "this_case"
    if any(word in question for word in ("attention", "need my", "urgent", "to do", "todo", "act on")):
        return "attention"
    if any(word in question for word in ("missing", "not attached", "no attachment", "without an si", "without a bl")):
        return "missing_documents"
    return None


def explicit_intent(question):
    if any(word in question for word in ("drift", "phish", "spam", "security")):
        return "safety"
    if any(word in question for word in ("correct", "field", "compare", "mismatch")):
        return "workflow"
    if any(word in question for word in ("waiting", "revision", "awaiting")):
        return "revisions"
    if any(word in question for word in ("attention", "progress", "status", "summary", "draft", "case", "email")):
        return "progress"
    return None


def email_link(item):
    return {"emailId": str(item["id"]), "label": item["display_id"]}


async def this_email(connection, workspace_id, email_id):
    rows = await load_inbox(connection, workspace_id, email_id)
    if not rows:
        return "I could not find this email. It may have been moved to Trash.", []
    item = rows[0]
    parts = [f"{item['display_id']}: {item['state_label']}."]
    if item["reasons"]:
        parts.append("Why: " + "; ".join(reason["label"] for reason in item["reasons"]) + ".")
    parts.append(f"Next step: {item['action']['title']}.")
    if item["category"] == "BL_COMPARISON":
        documents = item["documents"]
        parts.append(
            f"Shipping instructions {'found' if documents['si'] else 'not found'}; "
            f"draft BL {'found' if documents['bl'] else 'not found'}."
        )
    return " ".join(parts), [email_link(item)]


async def this_case(connection, workspace_id, case_id):
    row = await (
        await connection.execute(
            "select id,reference,readiness from public.cases where workspace_id=%s and id=%s", (workspace_id, case_id)
        )
    ).fetchone()
    if row is None:
        return "I could not find this case.", []
    return (
        f"Case {row['reference']} is {row['readiness'].replace('_', ' ')}. "
        "Open the field comparison to see each value with its source quote.",
        [{"caseId": str(row["id"])}],
    )


async def inbox_list(connection, workspace_id, intent):
    everything = await load_inbox(connection, workspace_id)
    if intent == "missing_documents":
        rows = [item for item in everything if item["state"] == "needs_documents"]
        if not rows:
            return "No email is missing its shipping instructions or draft BL right now.", []
        lines = "; ".join(f"{item['display_id']} ({item['reasons'][0]['label']})" for item in rows[:5])
        return f"{len(rows)} emails are missing documents. Most recent first: {lines}.", [email_link(i) for i in rows[:5]]
    rows = sorted(
        (item for item in everything if item["state"] in ATTENTION_ORDER),
        key=lambda item: ATTENTION_ORDER.index(item["state"]),
    )
    if not rows:
        return "Nothing needs a person right now.", []
    tally = ", ".join(
        f"{sum(item['state'] == state for item in rows)} {state.replace('_', ' ')}" for state in ATTENTION_ORDER
        if any(item["state"] == state for item in rows)
    )
    lines = "; ".join(f"{item['display_id']} ({item['state_label']})" for item in rows[:5])
    return f"{len(rows)} emails need a person: {tally}. Most urgent: {lines}.", [email_link(i) for i in rows[:5]]


@router.post("/chat")
async def chat(request: Request, ctx: Viewer, body: ChatMessage):
    question = body.message.strip().casefold()
    intent = page_intent(question, body.page) or explicit_intent(question)
    method, fallback_reason = "read_only_summary", None
    if intent is None:
        # AI can select an allowed intent; it cannot write facts or invent citations.
        provider = create_provider(request.app.state.settings)
        if provider:
            try:
                route, _ = await BoundedAI(
                    provider, request.app.state.database, ctx.workspace_id, request.app.state.settings
                ).call("route_question", body.message)
                intent, method = route.intent, "ai_routed_summary"
            except DomainError as exc:
                fallback_reason = exc.code
            finally:
                await provider.close()
        intent = intent or "unsupported"

    citations = []
    # No database connection is held while calling the external provider.
    async with request.app.state.database.connection() as connection:
        summary = await workspace_summary(connection, ctx.workspace_id)
        if intent == "this_email":
            answer, citations = await this_email(connection, ctx.workspace_id, body.page.email_id)
        elif intent == "this_case":
            answer, citations = await this_case(connection, ctx.workspace_id, body.page.case_id)
        elif intent in {"attention", "missing_documents"}:
            answer, citations = await inbox_list(connection, ctx.workspace_id, intent)
        elif intent == "safety":
            answer = f"Static safety checks assessed {summary['safety_assessed']} emails; {summary['safety_held']} are held for human review. {summary['spam_count']} emails are classified as spam. Drift status: {summary['drift_state']}. Open Alerts for evidence. These signals do not confirm phishing or concept drift."
        elif intent == "workflow":
            answer = "Open a case, confirm its SI and BL sources, then inspect seven field comparisons and source evidence. Preview a supported correction request and copy it to share. A returned draft needs extraction and source confirmation before verification. Uncertain values require review."
        elif intent in {"progress", "revisions"}:
            answer = (
                f"Your workspace has {summary['emails_total']} emails, "
                f"{summary['emails_classified']} classified, {summary['cases_open']} open cases, "
                f"{summary['cases_checked']} checked, {summary['review_queue_size']} needing a decision "
                f"and {summary['awaiting_revision']} awaiting revision. "
                f"{summary['jobs_in_progress']} processing jobs are queued or active."
            )
            states = ["awaiting_revision"] if intent == "revisions" else ["needs_decision", "changes_required", "failed", "needs_source"]
            rows = await (await connection.execute(
                """select id,reference,readiness from public.cases where workspace_id=%s
                and readiness=any(%s) order by updated_at desc limit 5""",
                (ctx.workspace_id, states),
            )).fetchall()
            if rows:
                answer += " Related cases: " + "; ".join(
                    f"{r['reference']} ({r['readiness'].replace('_', ' ')})" for r in rows
                ) + "."
                citations = [{"caseId": str(r["id"])} for r in rows]
        else:
            answer = "I can summarize workspace progress, list cases needing attention or awaiting revision, and explain document comparison. I do not have evidence to answer that question."
    return {
        "answer": answer, "citations": citations, "grounded_on": "workspace_data",
        "method": method, "fallback_reason": fallback_reason,
        "source": (
            {"label": "Inbox", "href": "/inbox"}
            if intent in {"this_email", "attention", "missing_documents"}
            else {"label": "Current workspace overview", "href": "/dashboard"}
        ),
    }
