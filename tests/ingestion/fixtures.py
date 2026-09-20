"""Real BOE responses, trimmed to a handful of blocks.

The XML fixtures are the actual answers of the API (downloaded on 2026-09-20), with most blocks
removed so the files stay small: what is left is untouched, including the seven historical
versions of LAU article 36 that make "pick the version in force" a real test rather than a
rehearsed one.

Edge cases the real documents do not contain (a block whose only version is dated in the
future, an article with no title) are written by hand in the tests that need them.
"""

import json
import pathlib
from typing import Any

FIXTURES = pathlib.Path(__file__).parent / "fixtures"

LAU = "BOE-A-1994-26003"
CATALONIA = "BOE-A-2008-3657"
STRESSED_AREAS = "BOE-A-2025-8636"

# The fixtures were downloaded on this date, so the "version in force" is resolved against it
# and the tests keep saying the same thing tomorrow.
TODAY = "20260920"


def xml(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


def metadata(name: str) -> dict[str, Any]:
    payload: dict[str, Any] = json.loads((FIXTURES / name).read_text(encoding="utf-8"))
    return payload
