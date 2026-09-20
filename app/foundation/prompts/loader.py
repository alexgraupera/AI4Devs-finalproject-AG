"""Jinja2 loader for versioned prompt templates.

Layout on disk: ``app/foundation/prompts/<use_case>/<version>/<role>.j2``. Versioning from
day one means switching prompts is a string at the call site (``version="v2"``), not a
refactor, and the diff between versions stays visible in the Git history.

``StrictUndefined`` turns a typo in a template variable into an error instead of a silently
empty prompt, which the model would answer anyway.
"""

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from app.domain.schemas.listing_review import Listing

_TEMPLATES_DIR = Path(__file__).resolve().parent

_env = Environment(
    loader=FileSystemLoader(_TEMPLATES_DIR),
    undefined=StrictUndefined,
    trim_blocks=True,
    lstrip_blocks=True,
    autoescape=False,
    keep_trailing_newline=True,
)


def render_listing_review_prompt(listing: Listing, version: str = "v1") -> tuple[str, str]:
    """Render the system and user prompts of the listing review use case.

    Returns:
        ``(system_prompt, user_prompt)``, ready to be sent as separate messages.
    """
    system = _env.get_template(f"listing_review/{version}/system.j2").render()
    user = _env.get_template(f"listing_review/{version}/user.j2").render(listing=listing)
    return system, user


def render_regulations_qa_prompt(question: str, context: str, version: str = "v1") -> tuple[str, str]:
    """Render the system and user prompts of the regulation Q&A use case."""
    system = _env.get_template(f"regulations_qa/{version}/system.j2").render()
    user = _env.get_template(f"regulations_qa/{version}/user.j2").render(question=question, context=context)
    return system, user


def render_regulations_query_prompt(question: str, version: str = "v1") -> tuple[str, str]:
    """Render the prompts that rewrite a question into the vocabulary of the regulations."""
    system = _env.get_template(f"regulations_query/{version}/system.j2").render()
    user = _env.get_template(f"regulations_query/{version}/user.j2").render(question=question)
    return system, user


def render_regulations_rerank_prompt(question: str, candidates: str, version: str = "v1") -> tuple[str, str]:
    """Render the prompts that score retrieved fragments against the question."""
    system = _env.get_template(f"regulations_rerank/{version}/system.j2").render()
    user = _env.get_template(f"regulations_rerank/{version}/user.j2").render(question=question, candidates=candidates)
    return system, user
