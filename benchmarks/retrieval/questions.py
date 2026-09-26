"""The golden set: the questions, and what each one should retrieve.

A question is identified by law and block, not by chunk id: chunk ids change every time the
corpus is re-ingested, and a golden set that has to be rewritten after every ingestion stops
being golden.
"""

import pathlib
from dataclasses import dataclass, field

import yaml

QUESTIONS_FILE = pathlib.Path(__file__).parent / "questions.yaml"


@dataclass(frozen=True)
class ExpectedChunk:
    law_id: str
    block_id: str


@dataclass(frozen=True)
class Question:
    id: str
    question: str
    expected: list[ExpectedChunk] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    # What a correct answer says, for judging the generated answer (#48). Out-of-domain
    # questions have none: the right answer is a refusal.
    reference: str | None = None

    @property
    def is_out_of_domain(self) -> bool:
        """No expected chunk means the corpus does not answer it, and silence is the right answer."""
        return not self.expected


def load_questions(path: pathlib.Path = QUESTIONS_FILE) -> list[Question]:
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    questions = [
        Question(
            id=entry["id"],
            question=entry["question"],
            expected=[ExpectedChunk(**expected) for expected in entry.get("expected") or []],
            tags=list(entry.get("tags") or []),
            reference=entry.get("reference"),
        )
        for entry in document["questions"]
    ]

    ids = [question.id for question in questions]
    duplicates = {id for id in ids if ids.count(id) > 1}
    if duplicates:
        raise ValueError(f"duplicate question ids in the golden set: {sorted(duplicates)}")
    return questions
