"""Regulation Q&A page. It only talks to the API over HTTP.

The citations are the point of this page, so they are rendered as links to the BOE article
rather than as a sentence the reader has to take on trust. The retrieved fragments and their
scores sit one click away: when an answer looks wrong, the first question is always what it was
built from.
"""

from typing import Any

import streamlit as st

from ui_api import WAKING_UP, is_api_available, post

JURISDICTIONS = {
    "Toda España": None,
    "Estatal": ["state"],
    "Cataluña": ["catalonia"],
}


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

with st.expander("Qué normativa puedo consultar"):
    st.markdown(
        """
        - **Ley 29/1994, de Arrendamientos Urbanos (LAU)**: fianza, duración, prórrogas,
          actualización de la renta, gastos, incumplimientos.
        - **Ley 12/2023, por el derecho a la vivienda**: información mínima al arrendatario,
          zonas de mercado residencial tensionado.
        - **Real Decreto 390/2021**: certificado y etiqueta de eficiencia energética.
        - **Ley 18/2007, del derecho a la vivienda (Cataluña)**: oferta de alquiler, cédula de
          habitabilidad, registro de fianzas.
        - **Resoluciones de zonas tensionadas** publicadas en el BOE.

        **Fuera de alcance**: fiscalidad del alquiler (IRPF), comunidades de propietarios,
        procedimientos judiciales de desahucio, seguros y normativa autonómica distinta de la
        catalana. Sobre eso el asistente dirá que no lo sabe, que es lo correcto.
        """
    )

with st.spinner(WAKING_UP):
    available = is_api_available()
if not available:
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
        body, error = post("/api/v1/regulations/ask", {"question": question, "jurisdictions": JURISDICTIONS[scope]})

    if error is not None:
        st.error(error)
    elif body is not None:
        render_answer(body)
