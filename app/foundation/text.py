"""Whether a quote a model gave really comes from a text: the model quotes, code checks.

Models copy with small slips (an accent, a quote mark, a changed article), so an exact substring
match would reject honest quotes. A quote passes when a single stretch of the text matches at least
`min_ratio` of it, after folding case, accents, punctuation and whitespace. An invented sentence
has no such stretch; a copied one with a slip does.

The limit: a slip and a negation weigh the same. "No incluye" and "incluye" differ by three
characters, so a quote that drops a "no" still passes here. This check stops invented sentences;
whether a real sentence supports a finding is the critic's job.
"""

import re
import unicodedata
from difflib import SequenceMatcher

DEFAULT_MIN_RATIO = 0.8


def fold(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text.casefold())
    without_accents = "".join(char for char in decomposed if not unicodedata.combining(char))
    return " ".join(re.sub(r"[^\w\s]", " ", without_accents).split())


def appears_in(quote: str, text: str, *, min_ratio: float = DEFAULT_MIN_RATIO) -> bool:
    needle, haystack = fold(quote), fold(text)
    if not needle:
        return False
    if needle in haystack:
        return True

    # The characters of the quote found in the text, counted only within one stretch of it about
    # the quote's length: a copy with a slip matches almost all of them there, while an invented
    # sentence built from the text's words matches them scattered, or not at all.
    # Blocks of one or two characters are coincidences ("i", "o"), not copying: in a short quote they
    # would add up to a pass for a sentence the text never contained.
    blocks = [b for b in SequenceMatcher(None, needle, haystack, autojunk=False).get_matching_blocks() if b.size >= 3]
    reach = int(len(needle) * 1.5)
    best = 0
    for i, first in enumerate(blocks):
        matched = 0
        for block in blocks[i:]:
            if block.b + block.size - first.b > reach:
                break
            matched += block.size
        best = max(best, matched)
    return best / len(needle) >= min_ratio
