"""Regulation Q&A page. It only talks to the API over HTTP.

The citations are the point of this page, so they are rendered as links to the BOE article
rather than as a sentence the reader has to take on trust. The retrieved fragments and their
scores sit one click away: when an answer looks wrong, the first question is always what it was
built from.
"""

from typing import Any

import httpx
import streamlit as st

from app.config import get_settings

UNEXPECTED_ERROR = "No se ha podido contactar con el servicio. Inténtalo de nuevo."

JURISDICTIONS = {
    "Toda España": None,
    "Estatal": ["state"],
    "Cataluña": ["catalonia"],
}


def is_api_available(api_url: str) -> bool:
    try:
        return httpx.get(f"{api_url}/health", timeout=2).status_code == 200
    except httpx.HTTPError:
        return False


def ask(api_url: str, payload: dict[str, Any]) -> tuple[dict[str, Any] | None, str | None]:
    """Returns (answer, error message). The API already words its errors for the person reading."""
    try:
        response = httpx.post(f"{api_url}/api/v1/regulations/ask", json=payload, timeout=120)
    except httpx.HTTPError:
        return None, UNEXPECTED_ERROR

    body = response.json()
    if response.is_success:
        return body, None
    return None, str(body.get("error", {}).get("message", UNEXPECTED_ERROR))


def render_sources(citations: list[dict[str, Any]]) -> None:
    st.subheader("Fuentes")
    for citation in citations:
        st.markdown(f"- [{citation['law_title']} · {citation['article']}]({citation['url']})")


def render_retrieved(retrieved: list[dict[str, Any]]) -> None:
    with st.expander("Fragmentos recuperados"):
        if not retrieved:
            st.caption("La búsqueda no ha devuelto ningún fragmento por encima del umbral.")
            return
        st.dataframe(
            [
                {
                    "Puntuación": round(chunk["score"], 3),
                    "Artículo": chunk["article_title"],
                    "Norma": chunk["law_id"],
                }
                for chunk in retrieved
            ],
            hide_index=True,
            use_container_width=True,
        )


def render_usage(usage: dict[str, Any]) -> None:
    if usage["attempts"] == 0:
        st.caption("Sin llamada al modelo: la normativa indexada no cubría la pregunta.")
        return
    cost = usage["estimated_cost_usd"]
    cost_text = f"{float(cost):.4f} USD" if cost is not None else "no disponible"
    st.caption(
        f"Modelo: {usage['model']} · {usage['input_tokens']} + {usage['output_tokens']} tokens "
        f"· {usage['latency_ms']} ms · Coste estimado: {cost_text}"
    )


def render_answer(body: dict[str, Any]) -> None:
    if body["has_answer"]:
        st.write(body["answer"])
        render_sources(body["citations"])
    else:
        st.warning(body["answer"])

    render_retrieved(body["retrieved"])
    render_usage(body["usage"])


st.set_page_config(page_title="Consulta sobre normativa de alquiler", page_icon="📖")
st.title("Consulta sobre normativa de alquiler")
st.caption(
    "Las respuestas salen únicamente de la normativa indexada del BOE y citan el artículo del que "
    "proceden. No es asesoramiento legal."
)

api_url = get_settings().api_url
if not is_api_available(api_url):
    st.error("API no disponible")
    st.stop()

with st.form("regulation_question"):
    question = st.text_area(
        "Tu pregunta",
        height=100,
        placeholder="¿Cuál es la fianza legal en un alquiler de vivienda?",
    )
    scope = st.selectbox("Ámbito", list(JURISDICTIONS), help="Restringe la búsqueda a una jurisdicción")
    submitted = st.form_submit_button("Consultar")

if submitted:
    if not question.strip():
        st.error("La pregunta está vacía")
        st.stop()

    with st.spinner("Buscando en la normativa..."):
        body, error = ask(api_url, {"question": question, "jurisdictions": JURISDICTIONS[scope]})

    if error is not None:
        st.error(error)
    elif body is not None:
        render_answer(body)
