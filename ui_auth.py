"""A shared username and password in front of the UI (added after the first public deploy).

The API has its own protection (service token, API key, rate limit, daily spend cap; ADR 0020).
This is the door of the UI: without it, anyone with the URL could run reviews on the owner's
provider balance, up to the daily cap. One shared user is enough for the owner and the evaluator.

- The credentials live in the environment (`UI_USERNAME`, `UI_PASSWORD`), set on the platform,
  never in the repository.
- **It fails closed.** In production, a missing username or password shows an error and nothing
  else: a forgotten variable must not quietly leave the UI open. In development, no credentials
  means no login, so the UI keeps working on a laptop with an empty `.env`.
- Every page calls `require_login()` right after `set_page_config`: a page reached by its own URL
  is guarded like the home page.
- Both values are compared in constant time, and five wrong attempts lock the session for a minute.
  A new browser session starts the count again, which is why the password should be long: the
  lock slows a person down, the length stops a script.
"""

import hmac
import time

import streamlit as st

from app.config import get_settings

MAX_ATTEMPTS = 5
LOCK_SECONDS = 60

TITLE = "Acceso"
NOT_CONFIGURED = "El acceso a la interfaz no está configurado: faltan UI_USERNAME o UI_PASSWORD en el despliegue."
WRONG = "Usuario o contraseña incorrectos."
LOCKED = "Demasiados intentos fallidos. Espera un minuto y vuelve a intentarlo."
SIGN_OUT = "Cerrar sesión"


def require_login() -> None:
    """Stop the page here unless the session has signed in (or no login is configured in development)."""
    settings = get_settings()
    username, password = settings.ui_username, settings.ui_password
    if not username or not password:
        if settings.environment == "production":
            st.error(NOT_CONFIGURED)
            st.stop()
        return
    if st.session_state.get("signed_in"):
        _sign_out_button()
        return

    st.title(TITLE)
    locked_until = float(st.session_state.get("locked_until", 0.0))
    if time.monotonic() < locked_until:
        st.error(LOCKED)
        st.stop()

    with st.form("login"):
        given_user = st.text_input("Usuario", key="login-user")
        given_password = st.text_input("Contraseña", type="password", key="login-password")
        submitted = st.form_submit_button("Entrar")
    if submitted:
        if _same(given_user, username) & _same(given_password, password):
            st.session_state["signed_in"] = True
            st.session_state.pop("failed_attempts", None)
            st.rerun()
        failures = int(st.session_state.get("failed_attempts", 0)) + 1
        st.session_state["failed_attempts"] = failures
        if failures >= MAX_ATTEMPTS:
            st.session_state["locked_until"] = time.monotonic() + LOCK_SECONDS
            st.session_state["failed_attempts"] = 0
            st.error(LOCKED)
        else:
            st.error(WRONG)
    st.stop()


def _same(given: str, expected: str) -> bool:
    # Constant time, and both fields always compared (`&`, not `and`): how long a wrong answer
    # takes says nothing about which half of it was wrong.
    return hmac.compare_digest(given.encode(), expected.encode())


def _sign_out_button() -> None:
    if st.sidebar.button(SIGN_OUT, key="sign-out"):
        st.session_state.clear()
        st.rerun()
