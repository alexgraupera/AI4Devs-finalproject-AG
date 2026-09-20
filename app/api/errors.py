"""Error mapping: the only place that turns a domain failure into an HTTP answer.

Every error leaves as `{"error": {"code", "message"}}`. The code is for the client to branch
on, the message is for the person to read, so it is written in Spanish.
"""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.domain.errors import CorpusUnavailable, LLMUnavailable, NotAListing, ReviewGenerationError
from app.foundation.guardrails.input import InputGuardrailViolation

MESSAGES: dict[str, str] = {
    "empty_text": "El anuncio está vacío",
    "text_too_short": "El texto es demasiado corto para ser un anuncio",
    "text_too_long": "El anuncio supera los 5.000 caracteres",
    "moderation": "El texto contiene contenido no permitido",
    "prompt_injection": "El texto contiene instrucciones sospechosas",
    "pii": "Quita los datos personales (email, teléfono o IBAN) del anuncio",
    "not_a_listing": "El texto no parece un anuncio de alquiler",
    "review_generation_failed": "No se ha podido generar la revisión. Inténtalo de nuevo.",
    "llm_unavailable": "El servicio de IA no está disponible en este momento",
    "corpus_unavailable": "La normativa no está disponible en este momento",
}


def error_response(code: str, status_code: int) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"error": {"code": code, "message": MESSAGES[code]}})


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(InputGuardrailViolation)
    async def _guardrail(_: Request, error: InputGuardrailViolation) -> JSONResponse:
        return error_response(error.reason, status_code=422)

    @app.exception_handler(NotAListing)
    async def _not_a_listing(_: Request, error: NotAListing) -> JSONResponse:
        return error_response("not_a_listing", status_code=422)

    @app.exception_handler(ReviewGenerationError)
    async def _generation(_: Request, error: ReviewGenerationError) -> JSONResponse:
        return error_response("review_generation_failed", status_code=502)

    @app.exception_handler(LLMUnavailable)
    async def _unavailable(_: Request, error: LLMUnavailable) -> JSONResponse:
        return error_response("llm_unavailable", status_code=503)

    @app.exception_handler(CorpusUnavailable)
    async def _corpus(_: Request, error: CorpusUnavailable) -> JSONResponse:
        return error_response("corpus_unavailable", status_code=503)
