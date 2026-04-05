import json
from collections.abc import Iterator

from openai import OpenAI
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.audit_log import AuditLog
from app.services.organization import _require_organization_admin

# Max rows injected into the LLM prompt (newest first) so requests stay small.
_MAX = 400
# Tells the model to stay grounded in the log lines we pass in.
_SYS = "Answer only from the audit logs below. If they lack data, say so."


def load_audit_logs_as_text(db: Session, org_id: int, actor) -> tuple[str, int]:
    """Ensure actor is org admin, then return logs as one JSON object per line plus row count."""
    _require_organization_admin(db, org_id, actor)
    rows = db.scalars(
        select(AuditLog)
        .where(AuditLog.org_id == org_id)
        .order_by(AuditLog.created_at.desc())
        .limit(_MAX)
    ).all()
    # One line per event so the model can scan structured fields easily.
    lines = [
        json.dumps(
            {
                "at": r.created_at.isoformat(),
                "action": r.action,
                "resource_type": r.resource_type,
                "resource_id": r.resource_id,
                "user_id": r.user_id,
                "details": r.details,
            },
            default=str,
        )
        for r in rows
    ]
    return "\n".join(lines), len(lines)


def _msgs(logs: str, question: str) -> list[dict[str, str]]:
    """Build OpenAI chat messages: system rules + user content (logs + question)."""
    return [
        {"role": "system", "content": _SYS},
        {"role": "user", "content": f"Logs (newest first, JSON per line):\n{logs}\n\n{question}"},
    ]


def _client() -> OpenAI | None:
    """SDK client if OPENAI_API_KEY is set; None means we skip the API and use fallbacks."""
    s = get_settings()
    if not s.openai_api_key:
        return None
    return OpenAI(api_key=s.openai_api_key, base_url=s.openai_base_url.rstrip("/") or None)


def answer_audit_question_sync(logs_text: str, question: str, log_count: int) -> str:
    """Non-streaming path: one API call, return the full assistant text (for JSON responses)."""
    c, s = _client(), get_settings()
    if not c:
        # No key configured — avoid calling OpenAI; still return something useful to the client.
        return f"[No OPENAI_API_KEY] {log_count} log rows. Q: {question!r}"
    # Single completion; choices[0].message.content is the model reply.
    r = c.chat.completions.create(model=s.openai_model, messages=_msgs(logs_text, question))
    return (r.choices[0].message.content or "").strip()


def stream_audit_answer(logs_text: str, question: str, log_count: int) -> Iterator[str]:
    """Streaming path: yield small text fragments as the model generates them (for chunked HTTP body)."""
    c, s = _client(), get_settings()
    if not c:
        yield f"[No OPENAI_API_KEY] {log_count} log rows. Q: {question!r}"
        return
    # stream=True returns an iterator; each event may carry a piece of the answer in delta.content.
    for ev in c.chat.completions.create(
        model=s.openai_model, messages=_msgs(logs_text, question), stream=True
    ):
        if ev.choices and (piece := ev.choices[0].delta.content):
            yield piece
