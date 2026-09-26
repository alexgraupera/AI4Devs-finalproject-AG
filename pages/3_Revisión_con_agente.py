"""Agent review page. It only talks to the API over HTTP.

Next to the plain review of page 1, on purpose: the same listing can be sent to both and compared.
What this page adds is where each finding came from (a link to the BOE article the agent read) and
the steps the agent took, one click away.
"""

from typing import Any

import streamlit as st

from ui_api import WAKING_UP, get, is_api_available, post
from ui_auth import require_login
from ui_feedback import render_feedback

SEVERITY_LABELS = {"high": "Alta", "medium": "Media", "low": "Baja"}
SEVERITY_ICONS = {"high": "🔴", "medium": "🟠", "low": "🟡"}
VERDICT_LABELS = {"approve": "Listo para publicar", "request_changes": "Requiere cambios"}
TOOL_LABELS = {
    "check_listing_fields": "Comprobar los datos del anuncio",
    "search_regulations": "Consultar la normativa",
    "submit_review": "Entregar la revisión",
    "critic": "Comprobación de las incidencias contra el anuncio y la normativa",
    "boss": "Decisión sobre la revisión",
    "rewrite": "Corregir el anuncio",
    "(sin herramienta)": "Respuesta sin herramienta",
}

# What a step marked as not ok means depends on the step: a failed tool call is not a critic that
# discarded a finding, and saying "failed and retried" of the latter is simply false.
FAILURE_NOTE = "Esta llamada ha fallado: el agente ha recibido el error y ha seguido."
FAILURE_NOTES = {
    "critic": "El revisor no respalda alguna incidencia; el motivo está debajo.",
    "rewrite": "El anuncio corregido tiene cifras que el original no tenía: revísalas antes de publicarlo.",
    "(sin herramienta)": "El agente contestó sin usar ninguna herramienta y se le pidió que entregara la revisión.",
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
                st.caption(FAILURE_NOTES.get(step["tool"], FAILURE_NOTE))
            if step["result"]:
                st.text(step["result"])


def render_rewrite(rewrite: dict[str, Any] | None) -> None:
    if rewrite is None:
        st.caption("El agente no ha propuesto una versión corregida.")
        return
    st.subheader("Anuncio corregido")
    if rewrite["placeholders"]:
        st.warning(
            "El agente no puede inventar estos datos. Complétalos antes de publicar: "
            + ", ".join(rewrite["placeholders"])
        )
    if rewrite["new_figures"]:
        st.warning(
            "Revisa estas cifras: aparecen en la versión corregida y no en tu anuncio: "
            + ", ".join(rewrite["new_figures"])
        )
    # The person publishing has the last word: the text is theirs to edit, and to copy.
    edited = st.text_area("Puedes editarlo antes de copiarlo", value=rewrite["text"], height=200, key="rewrite-text")
    st.code(edited, language=None)
    with st.expander("Cambios aplicados"):
        for change in rewrite["changes"]:
            st.markdown(f"- {change}")


def render_usage(usage: dict[str, Any]) -> None:
    cost = usage["estimated_cost_usd"]
    cost_text = f"{float(cost):.4f} USD" if cost is not None else "no disponible"
    st.caption(
        f"Modelo: {usage['model']} · {usage['input_tokens']} + {usage['output_tokens']} tokens "
        f"· {usage['latency_ms']} ms · Coste estimado: {cost_text}"
    )


STEP_LABELS = {
    "plan": "Razonamiento del agente",
    "tools": "Herramientas",
    "critic": "Revisor",
    "rewrite": "Anuncio corregido",
}


def render_cost_breakdown(steps: list[dict[str, Any]]) -> None:
    """Where the cost went: which step to make cheaper is read here, not guessed."""
    if not steps:
        return
    with st.expander("Coste por paso"):
        st.table(
            [
                {
                    "Paso": STEP_LABELS.get(step["step"], step["step"]),
                    "Llamadas": step["calls"],
                    "Tokens": step["input_tokens"] + step["output_tokens"],
                    "Tiempo": f"{step['latency_ms'] / 1000:.1f} s",
                    "Coste": f"{float(step['estimated_cost_usd']):.4f} USD"
                    if step["estimated_cost_usd"] is not None
                    else "no disponible",
                }
                for step in steps
            ]
        )


def render_pending(body: dict[str, Any]) -> None:
    """A review that waits for a person: what the agent proposes, what the critic rejected, and the decision."""
    pending = body["pending_review"]
    st.warning("El agente ha parado antes de publicar y espera tu decisión.")
    st.caption(f"Motivo: {pending['reason']}")

    proposed = pending["proposed"]["findings"]
    # A finding the critic doubted is either among the proposed ones, kept for you to decide (flag
    # mode), or already removed (filter mode): the same list says which.
    doubts = {rejected["message"]: rejected for rejected in pending["rejected"]}
    st.subheader("Incidencias propuestas")
    keep = []
    for index, finding in enumerate(proposed):
        doubt = doubts.get(finding["message"])
        label = f"{SEVERITY_ICONS.get(finding['severity'], '•')} {finding['message']}"
        if st.checkbox(
            label + (" · el revisor la pone en duda" if doubt else ""),
            value=True,
            key=f"keep-{pending['run_id']}-{index}",
        ):
            keep.append(index)
        if doubt:
            st.caption(f"Motivo del revisor: {doubt['reason']}")
    removed = [
        rejected for rejected in pending["rejected"] if rejected["message"] not in {f["message"] for f in proposed}
    ]
    if removed:
        with st.expander(f"Descartadas por el revisor ({len(removed)})"):
            for rejected in removed:
                st.markdown(f"- ~~{rejected['message']}~~")
                st.caption(f"{rejected['problem']}: {rejected['reason']}")

    note = st.text_input("Nota para el registro (opcional)", key=f"note-{pending['run_id']}")
    approve, adjust, reject = st.columns(3)
    decision = None
    if approve.button("Aprobar la revisión", type="primary"):
        decision = {"action": "approve", "note": note or None}
    if adjust.button("Publicar solo las marcadas"):
        decision = {"action": "adjust", "keep": keep, "note": note or None}
    if reject.button("Descartar la revisión"):
        decision = {"action": "reject", "note": note or None}

    if decision is not None:
        with st.spinner("Aplicando tu decisión..."):
            done, error = post(f"/api/v1/listings/agent-review/{pending['run_id']}/resume", decision)
        st.session_state.pop("agent_run_id", None)
        if error is not None:
            st.error(error)
        elif done is not None:
            st.session_state["agent_result"] = done
            st.rerun()
    render_trace(body["trace"])


def render_review(body: dict[str, Any]) -> None:
    if body["status"] == "discarded":
        st.info("Revisión descartada. No se ha publicado nada.")
        return
    if body["human_decision"] is not None:
        st.success("Revisión completada con tu decisión.")
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
    if body.get("disputed_findings"):
        with st.expander(f"El revisor pone en duda {len(body['disputed_findings'])} de estas incidencias"):
            for disputed in body["disputed_findings"]:
                st.markdown(f"- {disputed['message']}")
                st.caption(f"Motivo: {disputed['reason']}")
    render_rewrite(body["rewrite"])
    if body["dropped_findings"]:
        st.caption(
            f"Se han descartado {body['dropped_findings']} incidencias que el anuncio o la normativa "
            "consultada no respaldaban."
        )
    render_trace(body["trace"])
    render_usage(body["usage"])
    render_cost_breakdown(body.get("cost_breakdown", []))


st.set_page_config(page_title="Revisión con agente", page_icon="🕵️")
require_login()
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
    elif body is not None and body["status"] == "waiting_human":
        # Kept across reruns: a checkbox click reloads the page, and the pending decision must survive it.
        st.session_state["agent_run_id"] = body["run_id"]
        st.session_state.pop("agent_result", None)
    elif body is not None:
        st.session_state.pop("agent_run_id", None)
        st.session_state["agent_result"] = body

if "agent_run_id" in st.session_state:
    body, error = get(f"/api/v1/listings/agent-review/{st.session_state['agent_run_id']}")
    if error is not None:
        st.session_state.pop("agent_run_id", None)
        st.error(error)
    elif body is not None:
        render_pending(body)
elif "agent_result" in st.session_state:
    render_review(st.session_state["agent_result"])
    if st.session_state["agent_result"].get("status") != "discarded":
        render_feedback("agent_review", st.session_state["agent_result"].get("request_id"))
