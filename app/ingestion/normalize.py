"""Whitespace normalisation for BOE text.

The BOE mixes regular and non-breaking spaces inside the same sentence ("Artículo\xa031"), and
the XML carries the indentation of the document. Left alone, that noise reaches the embeddings
and the citations: "Artículo 36" and "Artículo\xa036" are different strings to everything
downstream, for a difference nobody can see.
"""


def normalize(text: str) -> str:
    return " ".join(text.split())
