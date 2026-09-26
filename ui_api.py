"""How the Streamlit pages talk to the API: one place for the URL, the credentials and the errors.

The client holds the service token and the API key the way a marketplace backend would, and sends
both on every call. A page never builds its own headers: three pages with three copies of the
credentials logic is how one of them ends up calling the API without them.
"""

from typing import Any

import httpx

from app.config import get_settings

UNEXPECTED_ERROR = "No se ha podido contactar con el servicio. Inténtalo de nuevo."


def api_url() -> str:
    return get_settings().api_url


def auth_headers() -> dict[str, str]:
    settings = get_settings()
    headers: dict[str, str] = {}
    if settings.service_token:
        headers["X-Service-Token"] = settings.service_token
    if settings.api_key:
        headers["X-API-Key"] = settings.api_key
    return headers


def is_api_available() -> bool:
    try:
        return httpx.get(f"{api_url()}/health", timeout=5).status_code == 200
    except httpx.HTTPError:
        return False


def post(path: str, payload: dict[str, Any], *, timeout: float = 120) -> tuple[dict[str, Any] | None, str | None]:
    """Returns (body, error message). The API already words its errors for the person reading."""
    try:
        response = httpx.post(f"{api_url()}{path}", json=payload, headers=auth_headers(), timeout=timeout)
    except httpx.HTTPError:
        return None, UNEXPECTED_ERROR

    try:
        body = response.json()
    except ValueError:
        return None, UNEXPECTED_ERROR
    if response.is_success:
        return body, None
    return None, str(body.get("error", {}).get("message", UNEXPECTED_ERROR))
