"""The output guardrail only trusts the sources the checklist teaches.

If a new article is added to the prompt but not to the allow-list, every finding citing it
would be silently dropped, and the model would look wrong when the configuration is.
"""

import re
from pathlib import Path

import pytest

from app.foundation.guardrails.output import ALLOWED_LEGAL_BASIS

CHECKLISTS = sorted(Path("app/foundation/prompts/listing_review").glob("v*/checklist.j2"))


@pytest.mark.parametrize("checklist", CHECKLISTS, ids=lambda path: path.parent.name)
def test_every_source_in_the_checklist_is_allowed_by_the_output_guardrail(checklist: Path) -> None:
    cited = set(re.findall(r"\(((?:LAU|RD|Ley)[^)]+)\)", checklist.read_text(encoding="utf-8")))

    assert cited == set(ALLOWED_LEGAL_BASIS)
