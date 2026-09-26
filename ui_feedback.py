"""The thumbs under every review and answer: one vote per result, sent with the id of its request (#51).

The result has to survive the rerun Streamlit does on every click, so the pages keep it in the
session and render it from there. The vote is sent from the buttons' callbacks, which run before
that rerun: the page that follows already shows the thanks instead of the buttons, so a result is
voted once.
"""

import streamlit as st

from ui_api import post

THANKS = "Gracias, lo usaremos para mejorar las revisiones."
COMMENT_PLACEHOLDER = "¿Qué ha fallado? (opcional)"


def render_feedback(kind: str, request_id: str | None) -> None:
    if not request_id:
        return
    keys = _keys(request_id)
    if st.session_state.get(keys["sent"]):
        st.caption(THANKS)
        return
    error = st.session_state.pop(keys["error"], None)
    if error:
        st.error(error)
    with st.form(f"feedback-{request_id}", border=False):
        st.text_input(
            "Comentario",
            placeholder=COMMENT_PLACEHOLDER,
            max_chars=500,
            label_visibility="collapsed",
            key=keys["comment"],
        )
        up, down = st.columns(2)
        up.form_submit_button("👍 Útil", width="stretch", on_click=_send, args=(kind, request_id, "up"))
        down.form_submit_button("👎 No es correcto", width="stretch", on_click=_send, args=(kind, request_id, "down"))


def _send(kind: str, request_id: str, rating: str) -> None:
    keys = _keys(request_id)
    comment = str(st.session_state.get(keys["comment"]) or "").strip() or None
    payload = {"request_id": request_id, "kind": kind, "rating": rating, "comment": comment}
    _, error = post("/api/v1/feedback", payload, timeout=15)
    if error is not None:
        st.session_state[keys["error"]] = error
    else:
        st.session_state[keys["sent"]] = True


def _keys(request_id: str) -> dict[str, str]:
    return {name: f"feedback-{name}-{request_id}" for name in ("sent", "error", "comment")}
