"""The output guardrail only trusts the sources the checklist teaches.

If a new article is added to the prompt but not to the allow-list, every finding citing it
would be silently dropped, and the model would look wrong when the configuration is.
"""

import re
from pathlib import Path

from app.foundation.guardrails.output import ALLOWED_LEGAL_BASIS

CHECKLIST = Path("app/foundation/prompts/listing_review/v2/checklist.j2").read_text(encoding="utf-8")


def test_every_source_in_the_checklist_is_allowed_by_the_output_guardrail() -> None:
    cited = set(re.findall(r"\(((?:LAU|RD|Ley)[^)]+)\)", CHECKLIST))

    assert cited == set(ALLOWED_LEGAL_BASIS)
