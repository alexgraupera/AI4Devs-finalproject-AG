"""Input guardrails: everything that must happen before spending a token.

Four layers, cheapest first, so an abusive or useless request is rejected before it reaches
the model:

1. Size limits: blank, too short to be a listing, or too long to be worth reviewing.
2. Prompt-injection heuristics: regex over known patterns. Cheap second line of defence;
   the first one is the prompt itself, which treats the listing as data (see v2).
3. PII heuristics: regex over emails, phone numbers and IBANs. Deliberately not exhaustive:
   it demonstrates the pattern, it is not a compliance-grade redactor.
4. Moderation: the provider's classifier over hate, violence and sexual content. It goes last
   because it is the only layer that leaves the process: a text the regexes already reject
   should not wait ~2 s for a network round trip to be told so.

Policy: every layer raises. We never silently fix the input, because the person publishing
needs to know what was wrong with their listing.
"""

import re
from typing import Literal, Protocol

MIN_LENGTH = 50
MAX_LENGTH = 5_000

Reason = Literal["empty_text", "text_too_short", "text_too_long", "moderation", "prompt_injection", "pii"]


class InputGuardrailViolation(Exception):
    """Raised when one of the input layers rejects the listing."""

    def __init__(self, message: str, *, reason: Reason) -> None:
        super().__init__(message)
        self.reason: Reason = reason


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
    ("phone", r"(?<!\d)(?:\+34[\s-]?)?[6-9]\d{2}[\s-]?\d{2}[\s-]?\d{2}[\s-]?\d{2}(?!\d)"),
    ("iban", r"\bES\d{2}[\s-]?(?:\d{4}[\s-]?){5}\b"),
]


def _check_size(text: str) -> None:
    stripped = text.strip()
    if not stripped:
        raise InputGuardrailViolation("The listing is empty", reason="empty_text")
    if len(stripped) < MIN_LENGTH:
        raise InputGuardrailViolation(
            f"The listing has {len(stripped)} characters, fewer than {MIN_LENGTH}", reason="text_too_short"
        )
    if len(stripped) > MAX_LENGTH:
        raise InputGuardrailViolation(
            f"The listing has {len(stripped)} characters, more than {MAX_LENGTH}", reason="text_too_long"
        )


def _check_injection(text: str) -> None:
    for pattern in _INJECTION_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            raise InputGuardrailViolation("The listing contains instruction-like text", reason="prompt_injection")


def _check_pii(text: str) -> None:
    for kind, pattern in _PII_PATTERNS:
        if re.search(pattern, text):
            raise InputGuardrailViolation(f"The listing contains personal data ({kind})", reason="pii")


async def check_input(text: str, moderation: ModerationClient | None = None) -> None:
    """Run every layer over the listing text. Raises `InputGuardrailViolation` on the first hit."""
    _check_size(text)
    _check_injection(text)
    _check_pii(text)
    if moderation is not None and await moderation.is_flagged(text):
        raise InputGuardrailViolation("The listing was flagged by moderation", reason="moderation")
