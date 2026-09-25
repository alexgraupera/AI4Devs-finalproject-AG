"""Which role may call which tool, as data, and the audit of every call.

**The check sits in front of the executor, not in the prompt.** A rule that lives only in a system
prompt is a rule the model may decline to follow, and a prompt injection in a pasted listing is
exactly the kind of text that talks a model into calling something else. A denied call never
reaches the tool: the model reads a refusal, and the audit records it.

**Deny by default.** A tool registered without being granted to a role is refused, so adding a tool
is a refusal until someone decides who may use it, not an open door. Today only the reviewer calls
tools; the critic and the rewriter read and write text and call none. That is the point of writing it
down: when a tool with side effects arrives (publishing a listing, calling the Catastro), the table
says who may use it before any prompt does.

**Every call is audited**: role, tool, outcome, latency, and the arguments redacted. A listing can
carry personal data and an audit log is not a place to accumulate it, so only the names, types and
lengths of the arguments are kept, plus the search query, the one argument worth reading back. Many
denials from one run are a signal worth alerting on: they are what an injection attempt looks like.
"""

from enum import StrEnum
from typing import Any

import structlog

log = structlog.get_logger()

QUERY_CHARS = 200


class AgentRole(StrEnum):
    REVIEWER = "reviewer"
    CRITIC = "critic"
    REWRITER = "rewriter"


class AuditOutcome(StrEnum):
    ALLOWED = "allowed"
    DENIED = "denied"
    FAILED = "failed"


TOOL_PERMISSIONS: dict[AgentRole, frozenset[str]] = {
    AgentRole.REVIEWER: frozenset({"check_listing_fields", "search_regulations", "submit_review"}),
    AgentRole.CRITIC: frozenset(),
    AgentRole.REWRITER: frozenset(),
}


def may_call(role: AgentRole, tool: str) -> bool:
    return tool in TOOL_PERMISSIONS.get(role, frozenset())


def redact(arguments: dict[str, Any]) -> dict[str, Any]:
    """What an audit may keep of a call's arguments: their shape, and the search query."""
    kept: dict[str, Any] = {}
    for name, value in arguments.items():
        if name == "query" and isinstance(value, str):
            kept[name] = value[:QUERY_CHARS]
        elif isinstance(value, str | list | dict):
            kept[name] = f"<{type(value).__name__}, {len(value)}>"
        else:
            kept[name] = f"<{type(value).__name__}>"
    return kept


def audit(role: AgentRole, tool: str, outcome: AuditOutcome, *, arguments: dict[str, Any], latency_ms: int = 0) -> None:
    log.info(
        "agent.audit",
        role=role,
        tool=tool,
        outcome=outcome,
        arguments=redact(arguments),
        latency_ms=latency_ms,
    )
