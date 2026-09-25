"""Agent review page. It only talks to the API over HTTP.

Next to the plain review of page 1, on purpose: the same listing can be sent to both and compared.
What this page adds is where each finding came from (a link to the BOE article the agent read) and
the steps the agent took, one click away.
"""

from typing import Any

import streamlit as st

from ui_api import WAKING_UP, is_api_available, post

SEVERITY_LABELS = {"high": "Alta", "medium": "Media", "low": "Baja"}
SEVERITY_ICONS = {"high": "🔴", "medium": "🟠", "low": "🟡"}
VERDICT_LABELS = {"approve": "Listo para publicar", "request_changes": "Requiere cambios"}
TOOL_LABELS = {
    "check_listing_fields": "Comprobar los datos del anuncio",
    "search_regulations": "Consultar la normativa",
    "submit_review": "Entregar la revisión",
    "critic": "Comprobación de las incidencias contra el anuncio y la normativa",
    "boss": "Decisión sobre la revisión",
    "(sin herramienta)": "Respuesta sin herramienta",
}


def render_findings(findings: list[dict[str, Any]]) -> None:
    if not findings:
        st.info("No se han detectado incidencias.")
        return
    st.subheader(f"Incidencias ({len(findings)})")
    for finding in findings:
        severity = finding["severity"]
        with st.expander(f"{SEVERITY_ICONS.get(severity, '•')} {finding['message']}", expanded=severity == "high"):
            st.caption(f"Gravedad: {SEVERITY_LABELS.get(severity, severity)}")
            st.write(f"**Sugerencia:** {finding['suggestion']}")
            if finding["legal_basis"]:
                st.caption(f"Base legal: {finding['legal_basis']}")
            for citation in finding["citations"]:
                st.markdown(f"- [{citation['law_title']} · {citation['article']}]({citation['url']})")


def render_trace(trace: list[dict[str, Any]]) -> None:
    with st.expander(f"Pasos del agente ({len(trace)})"):
        for step in trace:
            label = TOOL_LABELS.get(step["tool"], step["tool"])
            icon = "✅" if step["ok"] else "⚠️"
            st.markdown(f"**{step['step']}. {icon} {label}**")
            st.caption(f"Herramienta: {step['tool']} · {step['latency_ms']} ms")
            if step.get("thought"):
                st.write(f"_{step['thought']}_")
            if step["arguments"]:
                st.json(step["arguments"], expanded=False)
            if not step["ok"]:
                st.caption("Esta consulta ha fallado y el agente lo ha reintentado.")
            if step["result"]:
                st.text(step["result"])


def render_usage(usage: dict[str, Any]) -> None:
    cost = usage["estimated_cost_usd"]
    cost_text = f"{float(cost):.4f} USD" if cost is not None else "no disponible"
    st.caption(
        f"Modelo: {usage['model']} · {usage['input_tokens']} + {usage['output_tokens']} tokens "
        f"· {usage['latency_ms']} ms · Coste estimado: {cost_text}"
    )


def render_review(body: dict[str, Any]) -> None:
    if body["escalated"]:
        st.error(
            "Esta revisión necesita una comprobación humana: el agente no ha podido respaldar todas "
            "sus conclusiones con la normativa."
        )
    if body["stop_reason"] != "completed":
        st.warning("El agente ha alcanzado el límite de pasos. La revisión puede estar incompleta.")
    if body["verdict"] == "approve":
        st.success(VERDICT_LABELS["approve"])
    else:
        st.warning(VERDICT_LABELS["request_changes"])
    st.write(body["summary"])
    render_findings(body["findings"])
    if body["dropped_findings"]:
        st.caption(
            f"Se han descartado {body['dropped_findings']} incidencias que el anuncio o la normativa "
            "consultada no respaldaban."
        )
    render_trace(body["trace"])
    render_usage(body["usage"])


st.set_page_config(page_title="Revisión con agente", page_icon="🕵️")
st.title("Revisión con agente")
st.caption("El agente consulta la normativa antes de decidir. Puedes ver cada paso que ha dado.")

with st.spinner(WAKING_UP):
    available = is_api_available()
if not available:
    st.error("API no disponible")
    st.stop()

with st.form("agent_review"):
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
    submitted = st.form_submit_button("Revisar con agente")

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
    with st.spinner("El agente está revisando el anuncio..."):
        body, error = post("/api/v1/listings/agent-review", listing)

    if error is not None:
        st.error(error)
    elif body is not None:
        render_review(body)
