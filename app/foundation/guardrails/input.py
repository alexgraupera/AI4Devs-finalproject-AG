"""Input guardrails: everything that must happen before spending a token.

Four layers, cheapest first, so an abusive or useless request is rejected before it reaches
the model:

1. Size limits: blank, too short to be meaningful, or too long to be worth processing. What
   counts as too short depends on the use case: see `SizeLimits`.
2. Prompt-injection heuristics: regex over known patterns. Cheap second line of defence;
   the first one is the prompt itself, which treats the listing as data (see v2).
3. PII heuristics: regex over emails, phone numbers and IBANs. Deliberately not exhaustive:
   it demonstrates the pattern, it is not a compliance-grade redactor.
4. Moderation: the provider's classifier over hate, violence and sexual content. It goes last
   because it is the only layer that leaves the process: a text the regexes already reject
   should not wait ~2 s for a network round trip to be told so.

Policy: every layer raises. We never silently fix the input, because the person publishing
needs to know what was wrong with what they sent.
"""

import re
from dataclasses import dataclass
from typing import Literal, Protocol

import structlog

log = structlog.get_logger()

Reason = Literal["empty_text", "text_too_short", "text_too_long", "moderation", "prompt_injection", "pii"]


@dataclass(frozen=True)
class SizeLimits:
    """What counts as too short or too long depends on what is being sent.

    A listing under 50 characters is not a listing; a question of 20 is a perfectly good
    question. Sharing one limit between the two would reject "¿Cuál es la fianza?".
    """

    minimum: int
    maximum: int


LISTING = SizeLimits(minimum=50, maximum=5_000)
QUESTION = SizeLimits(minimum=10, maximum=1_000)

# Kept for the callers that still import them: the listing limits are the historical ones.
MIN_LENGTH = LISTING.minimum
MAX_LENGTH = LISTING.maximum


class InputGuardrailViolation(Exception):
    """Raised when one of the input layers rejects the input."""

    def __init__(self, message: str, *, reason: Reason, limit: int | None = None) -> None:
        super().__init__(message)
        self.reason: Reason = reason
        # The number the text broke, so the message shown can name it instead of guessing.
        self.limit = limit


class ModerationClient(Protocol):
    async def is_flagged(self, text: str) -> bool: ...


# Patterns seen in real injection attempts, in Spanish and English. A listing has no reason
# to talk about instructions, prompts or roles.
_INJECTION_PATTERNS = [
    r"ignor[ae]\s+(las\s+)?(instrucciones|indicaciones|reglas)",
    r"olvida\s+(las\s+)?(instrucciones|reglas)",
    r"ignore\s+(all\s+)?(previous|prior|above)\s+instructions",
    r"disregard\s+(the\s+)?(previous|above)",
    r"(system|developer)\s+(prompt|message)",
    r"prompt\s+de\s+sistema",
    r"actúa\s+como\s+(si\s+)?",
    r"act\s+as\s+(if\s+)?",
    r"eres\s+ahora\s+",
    r"you\s+are\s+now\s+",
    r"aprueba\s+este\s+anuncio\s+sin",
    r"</?(listing|anuncio)>",
]

_PII_PATTERNS: list[tuple[str, str]] = [
    ("email", r"[\w.+-]+@[\w-]+\.[\w.]+"),
    # Nine digits starting with 6-9, however they are grouped: "612 345 678" (the usual way to
    # write a mobile), "612 34 56 78", "91 512 34 56", with spaces, dots or dashes.
    ("phone", r"(?<!\d)(?:\+34[\s.-]?)?[6-9](?:[\s.-]?\d){8}(?!\d)"),
    ("iban", r"\bES\d{2}[\s-]?(?:\d{4}[\s-]?){5}\b"),
]


def _check_size(text: str, limits: SizeLimits) -> None:
    stripped = text.strip()
    if not stripped:
        raise InputGuardrailViolation("The text is empty", reason="empty_text")
    if len(stripped) < limits.minimum:
        raise InputGuardrailViolation(
            f"The text has {len(stripped)} characters, fewer than {limits.minimum}",
            reason="text_too_short",
            limit=limits.minimum,
        )
    if len(stripped) > limits.maximum:
        raise InputGuardrailViolation(
            f"The text has {len(stripped)} characters, more than {limits.maximum}",
            reason="text_too_long",
            limit=limits.maximum,
        )


def _check_injection(text: str) -> None:
    for pattern in _INJECTION_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            raise InputGuardrailViolation("The text contains instruction-like text", reason="prompt_injection")


def _check_pii(text: str) -> None:
    for kind, pattern in _PII_PATTERNS:
        if re.search(pattern, text):
            raise InputGuardrailViolation(f"The text contains personal data ({kind})", reason="pii")


async def check_input(text: str, moderation: ModerationClient | None = None, *, limits: SizeLimits = LISTING) -> None:
    """Run every layer over the text. Raises `InputGuardrailViolation` on the first hit.

    Every rejection is logged with its reason and the length of the text, never the text: a burst
    of `prompt_injection` from one caller is a signal worth counting, and the text is exactly what
    may carry the personal data that got it rejected.
    """
    try:
        _check_size(text, limits)
        _check_injection(text)
        _check_pii(text)
        if moderation is not None and await moderation.is_flagged(text):
            raise InputGuardrailViolation("The listing was flagged by moderation", reason="moderation")
    except InputGuardrailViolation as violation:
        log.info("guardrail.rejected", reason=violation.reason, text_chars=len(text))
        raise
