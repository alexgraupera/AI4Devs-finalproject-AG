from typing import Any

import streamlit as st

from ui_api import WAKING_UP, is_api_available, post

SEVERITY_LABELS = {"high": "Alta", "medium": "Media", "low": "Baja"}
SEVERITY_ICONS = {"high": "🔴", "medium": "🟠", "low": "🟡"}
VERDICT_LABELS = {"approve": "Listo para publicar", "request_changes": "Requiere cambios"}


def render_usage(usage: dict[str, Any], cached: bool) -> None:
    if cached:
        st.caption("Respuesta cacheada · sin coste")
        return

    cost = usage["estimated_cost_usd"]
    cost_text = f"{float(cost):.4f} USD" if cost is not None else "no disponible"
    st.caption(
        f"Modelo: {usage['model']} · {usage['input_tokens']} + {usage['output_tokens']} tokens "
        f"· {usage['latency_ms']} ms · Coste estimado: {cost_text}"
    )


def render_review(review: dict[str, Any]) -> None:
    verdict = review["verdict"]
    label = VERDICT_LABELS.get(verdict, verdict)
    if verdict == "approve":
        st.success(label)
    else:
        st.warning(label)
    st.write(review["summary"])

    findings = review["findings"]
    if not findings:
        st.info("No se han detectado incidencias.")
        render_usage(review["usage"], review["cached"])
        return

    st.subheader(f"Incidencias ({len(findings)})")
    for finding in findings:
        severity = finding["severity"]
        icon = SEVERITY_ICONS.get(severity, "•")
        title = f"{icon} {finding['message']}"
        with st.expander(title, expanded=severity == "high"):
            st.caption(f"Gravedad: {SEVERITY_LABELS.get(severity, severity)}")
            st.write(f"**Sugerencia:** {finding['suggestion']}")
            if finding["legal_basis"]:
                st.caption(f"Base legal: {finding['legal_basis']}")

    render_usage(review["usage"], review["cached"])


st.set_page_config(page_title="Revisión de anuncios de alquiler", page_icon="🏠")
st.title("Revisión de anuncios de alquiler")

with st.spinner(WAKING_UP):
    available = is_api_available()
if not available:
    st.error("API no disponible")
    st.stop()

with st.form("listing_review"):
    text = st.text_area("Pega aquí tu anuncio", height=220)
    left, right = st.columns(2)
    with left:
        price = st.number_input("Precio (€/mes)", min_value=0.0, step=50.0, value=None)
        surface = st.number_input("Superficie útil (m²)", min_value=0.0, step=1.0, value=None)
        rooms = st.number_input("Habitaciones", min_value=0, step=1, value=None)
    with right:
        municipality = st.text_input("Municipio")
        energy_rating = st.selectbox(
            "Calificación energética",
            ["", "A", "B", "C", "D", "E", "F", "G", "En trámite", "Exenta"],
        )
    submitted = st.form_submit_button("Revisar anuncio")

if submitted:
    if not text.strip():
        st.error("El anuncio está vacío")
        st.stop()

    listing = {
        "text": text,
        "price_eur_month": price,
        "usable_surface_m2": surface,
        "rooms": rooms,
        "municipality": municipality or None,
        "energy_rating": energy_rating or None,
    }
    with st.spinner("Revisando el anuncio..."):
        review, error = post("/api/v1/listings/review", listing)

    if error is not None:
        st.error(error)
    elif review is not None:
        render_review(review)
