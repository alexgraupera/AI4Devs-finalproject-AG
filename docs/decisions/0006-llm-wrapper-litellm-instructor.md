# 0006. One wrapper for every LLM call: LiteLLM and Instructor

- **Status**: Accepted
- **Date**: 2026-09-20
- **Issue**: #8 (part of #1)

## Context

Every call to a model needs the same things: pick a provider, send system and user messages, get an answer that fits a schema, and retry when it does not. Doing that at each call site couples the domain to one SDK and duplicates the error handling.

## Options considered

- **Provider SDK directly** (`anthropic`, `openai`): fewer dependencies, but changing model or provider means rewriting calls, response parsing and error handling.
- **A hand-written adapter per provider**: portable, but it grows into maintaining rate limits, token accounting and response normalisation ourselves.
- **LiteLLM** as the normalisation layer, plus **Instructor** for validated structured output.
- **LangChain**: solves this as part of a much larger framework, oversized for the job.

## Decision

- **A single `LLMWrapper`** in `app/foundation/llm/wrapper.py` is the only place that imports `litellm`. The domain depends on the `StructuredLLM` protocol (`complete_structured`), so tests fake it without touching the network and no layer above knows which provider answered.
- **LiteLLM** normalises the call: the model is configuration (`LLM_MODEL=anthropic/claude-haiku-4-5`), and switching provider is an environment variable. Its `Router` gives the fallback we add in #10 for free.
- **Instructor** validates the answer against the Pydantic schema and re-prompts on failure, instead of us parsing JSON and writing the retry loop.
- **Default model: Claude Haiku 4.5**, the cheap and fast tier. The review is a short, well-specified task on a small context, and the project runs on API credits; a bigger model is a measured decision, not a default. #10 adds the fallback and the cost per call that make that comparison possible.
- **`litellm`, `instructor` and `jinja2` are pinned to exact versions.** A dependency in the path of every request is one a compromised or breaking release reaches silently; they get bumped deliberately, with the lockfile as evidence.

## Consequences

- One place to add fallback, cost accounting, caching and logging, which is exactly what the next phases do.
- We inherit LiteLLM's model naming and its bugs; the pin keeps that surface stable between deliberate upgrades.
- Structured output costs a retry when the model answers badly. That is visible in the logs and the cost, which is better than a parse error in front of the user.
