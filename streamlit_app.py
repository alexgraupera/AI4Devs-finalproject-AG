from typing import Any

import httpx
import streamlit as st

from app.config import get_settings

SEVERITY_LABELS = {"high": "Alta", "medium": "Media", "low": "Baja"}
SEVERITY_ICONS = {"high": "🔴", "medium": "🟠", "low": "🟡"}
VERDICT_LABELS = {"approve": "Listo para publicar", "request_changes": "Requiere cambios"}


def is_api_available(api_url: str) -> bool:
    try:
        response = httpx.get(f"{api_url}/health", timeout=2)
    except httpx.HTTPError:
        return False
    return response.status_code == 200


def review_listing(api_url: str, listing: dict[str, Any]) -> dict[str, Any] | None:
    """Returns the review, or None when the service could not answer."""
    try:
        response = httpx.post(f"{api_url}/api/v1/listings/review", json=listing, timeout=120)
        response.raise_for_status()
    except httpx.HTTPError:
        return None
    return response.json()  # type: ignore[no-any-return]


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


st.set_page_config(page_title="Revisión de anuncios de alquiler", page_icon="🏠")
st.title("Revisión de anuncios de alquiler")

api_url = get_settings().api_url
if not is_api_available(api_url):
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
        review = review_listing(api_url, listing)

    if review is None:
        st.error("No se ha podido generar la revisión. Inténtalo de nuevo.")
    else:
        render_review(review)
