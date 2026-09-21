"""What can go wrong in a review, expressed once so every layer above agrees on the vocabulary."""


class NotAListing(Exception):
    """The model read the text and it is not a rental listing."""


class ReviewGenerationError(Exception):
    """The model never produced an answer matching the schema, retries included."""


class LLMUnavailable(Exception):
    """The provider could not be reached: timeout, rate limit or server error."""


class CorpusUnavailable(Exception):
    """The regulation corpus is not configured or not reachable: nothing to retrieve from."""


class Unauthorized(Exception):
    """The caller did not present a valid API key for the retrieval endpoints."""
