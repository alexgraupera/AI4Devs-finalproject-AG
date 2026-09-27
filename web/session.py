"""The shared login of the demo, moved from the Streamlit client to the web server (ADR 0034, ADR 0036).

The pages are public: fictional listings cost nothing to show. What costs is a tool, a model call
paid from the owner's provider balance, so every forwarded `/api/*` call needs a session.

- **One shared user**, from the environment (`UI_USERNAME`, `UI_PASSWORD`), for the owner and the
  evaluator. Both values are compared in constant time, and both are always compared.
- **The session is a signed cookie**: the expiry, and an HMAC-SHA256 over it and the username with
  `SESSION_SECRET`. Nothing is stored on the server, so a restart or a second instance keeps every
  session; changing the secret or the username signs everyone out. `HttpOnly` keeps it from scripts,
  `SameSite=Strict` from other sites' forms, `Secure` in production from plain HTTP.
- **Five wrong attempts lock the client for a minute.** The lock is per client address and in
  memory: it slows a person down; the length of the password is what stops a script.
- **It fails closed.** In production, a missing username, password or secret answers every session
  and tool call with 503: a forgotten variable must not leave the tools open. In development, no
  credentials means no login, so the project runs on a laptop with an empty `.env`.
"""

import hashlib
import hmac
import secrets
import time
from collections.abc import Callable
from dataclasses import dataclass, field

from fastapi import Request
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel

from app.config import Settings

COOKIE = "umbral_session"
SESSION_SECONDS = 12 * 60 * 60
MAX_ATTEMPTS = 5
LOCK_SECONDS = 60

NOT_CONFIGURED = (
    "El acceso a la demo no está configurado: faltan UI_USERNAME, UI_PASSWORD o SESSION_SECRET en el despliegue."
)
WRONG = "Usuario o contraseña incorrectos."
LOCKED = "Demasiados intentos fallidos. Espera un minuto y vuelve a intentarlo."
SIGN_IN_REQUIRED = "Inicia sesión para usar las herramientas."

Clock = Callable[[], float]


class Credentials(BaseModel):
    username: str
    password: str


def sign(secret: str, username: str, expires: int) -> str:
    signature = hmac.new(secret.encode(), f"{username}|{expires}".encode(), hashlib.sha256).hexdigest()
    return f"{expires}.{signature}"


def _same(given: str, expected: str) -> bool:
    return hmac.compare_digest(given.encode(), expected.encode())


def _error(code: str, message: str, status_code: int, headers: dict[str, str] | None = None) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"error": {"code": code, "message": message}}, headers=headers)


def client_address(request: Request) -> str:
    """The client as the platform's proxy saw it: the last address it appended, not one the client wrote."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[-1].strip()
    return request.client.host if request.client else "unknown"


@dataclass
class SessionGuard:
    settings: Settings
    clock: Clock = time.time
    # Failures and lock expiry per client address, in memory: one instance, one demo.
    _failures: dict[str, int] = field(default_factory=dict)
    _locked_until: dict[str, float] = field(default_factory=dict)
    _dev_secret: str = field(default_factory=lambda: secrets.token_urlsafe(32))

    @property
    def login_required(self) -> bool:
        return bool(self.settings.ui_username and self.settings.ui_password)

    @property
    def misconfigured(self) -> bool:
        s = self.settings
        return s.environment == "production" and not (s.ui_username and s.ui_password and s.session_secret)

    @property
    def _secret(self) -> str:
        # In development a login can run without a secret: a per-process one signs its sessions, and a
        # restart signs everyone out. Production never gets here without its own (`misconfigured`).
        return self.settings.session_secret or self._dev_secret

    def signed_in(self, request: Request) -> bool:
        cookie = request.cookies.get(COOKIE, "")
        expires_text, _, _ = cookie.partition(".")
        if not expires_text.isdigit() or int(expires_text) <= self.clock():
            return False
        return _same(cookie, sign(self._secret, self.settings.ui_username, int(expires_text)))

    def refusal(self, request: Request) -> JSONResponse | None:
        """Why a tool call may not go through, or None when it may."""
        if self.misconfigured:
            return _error("not_configured", NOT_CONFIGURED, 503)
        if self.login_required and not self.signed_in(request):
            return _error("sign_in_required", SIGN_IN_REQUIRED, 401)
        return None

    def state(self, request: Request) -> Response:
        if self.misconfigured:
            return _error("not_configured", NOT_CONFIGURED, 503)
        return JSONResponse({"login_required": self.login_required, "signed_in": self.signed_in(request)})

    def sign_in(self, request: Request, credentials: Credentials) -> Response:
        if self.misconfigured:
            return _error("not_configured", NOT_CONFIGURED, 503)
        if not self.login_required:
            return Response(status_code=204)

        client = client_address(request)
        now = self.clock()
        if self._locked_until.get(client, 0.0) > now:
            return self._locked(client, now)

        # Both always compared (`&`, not `and`): how long a wrong answer takes says nothing about
        # which half of it was wrong.
        right = _same(credentials.username, self.settings.ui_username) & _same(
            credentials.password, self.settings.ui_password
        )
        if not right:
            failures = self._failures.get(client, 0) + 1
            self._failures[client] = failures
            if failures >= MAX_ATTEMPTS:
                self._failures.pop(client, None)
                self._locked_until[client] = now + LOCK_SECONDS
                return self._locked(client, now)
            return _error("wrong_credentials", WRONG, 401)

        self._failures.pop(client, None)
        self._locked_until.pop(client, None)
        expires = int(now) + SESSION_SECONDS
        response = Response(status_code=204)
        response.set_cookie(
            COOKIE,
            sign(self._secret, self.settings.ui_username, expires),
            max_age=SESSION_SECONDS,
            httponly=True,
            samesite="strict",
            secure=self.settings.environment == "production",
            path="/",
        )
        return response

    def sign_out(self) -> Response:
        response = Response(status_code=204)
        response.delete_cookie(COOKIE, path="/", httponly=True, samesite="strict")
        return response

    def _locked(self, client: str, now: float) -> JSONResponse:
        retry_after = max(1, int(self._locked_until[client] - now))
        return _error("locked", LOCKED, 429, headers={"Retry-After": str(retry_after)})
