"""The agent: reason, act, observe, repeat. Written by hand, on purpose.

The whole cycle fits on one screen, every decision is a plain `if`, and a wrong tool call is
debugged with a breakpoint. #41 re-expresses exactly this flow as a graph, and can then say what
the graph bought, measured against something that already worked.

How a run ends:

- **`submit_review`**: the model hands in its review through a tool whose parameters are the review
  schema. Validated here; an invalid one goes back to the model as an error to fix. Ending on a
  tool rather than on free text means the review is structured by construction.
- **The iteration limit**, the **time limit**, or **the same call failing twice**: the model is then
  made to submit what it has, once, and the review says it may be incomplete. A loop without a
  hard exit is how an agent burns a budget on a question it cannot answer.

Every step, tool errors included, lands in the trace.
"""

import json
import time
from dataclasses import dataclass, field
from typing import Any

import structlog
from pydantic import ValidationError

from app.domain.errors import ReviewGenerationError
from app.domain.schemas.listing_agent_review import AgentReviewCandidate, StopReason, TraceStep
from app.domain.schemas.listing_review import Listing
from app.foundation.llm.tools import RequestedToolCall, ToolCallingLLM, ToolSpec
from app.foundation.llm.usage import LLMUsage, combined
from app.foundation.prompts.loader import render_agent_review_prompt
from app.generation.agentic.policy import AgentRole, AuditOutcome, audit, may_call
from app.generation.agentic.ports import RegulationFragment
from app.generation.agentic.tools import Tool, ToolResult

log = structlog.get_logger()

SUBMIT = "submit_review"
DEFAULT_MAX_ITERATIONS = 6
DEFAULT_TIMEOUT_SECONDS = 90.0
RESULT_PREVIEW_CHARS = 400

NUDGE_TO_SUBMIT = (
    "No has llamado a ninguna herramienta. Si ya tienes la revisión, entrégala con submit_review; "
    "si te falta consultar algo, llama a la herramienta que corresponda."
)
MALFORMED_ARGUMENTS = "Los argumentos no son JSON válido. Vuelve a llamar con un objeto JSON."
TOOL_FAILED = "La herramienta ha fallado ({error}). Prueba otra cosa."
FINAL_CALL = (
    "Se ha acabado el margen de pasos. Entrega ahora la revisión con submit_review, solo con lo que "
    "ya has comprobado: no añadas incidencias legales que no hayas consultado."
)


def _inline_refs(schema: dict[str, Any]) -> dict[str, Any]:
    """Pydantic nests models under `$defs`; tool schemas are safer flat, whatever the provider."""
    definitions = schema.pop("$defs", {})

    def resolve(node: Any) -> Any:
        if isinstance(node, dict):
            if "$ref" in node:
                return resolve(dict(definitions[node["$ref"].split("/")[-1]]))
            return {key: resolve(value) for key, value in node.items()}
        if isinstance(node, list):
            return [resolve(item) for item in node]
        return node

    resolved: dict[str, Any] = resolve(schema)
    return resolved


SUBMIT_SPEC = ToolSpec(
    name=SUBMIT,
    description=(
        "Entrega la revisión terminada. Llámala una sola vez, al final, cuando hayas comprobado los "
        "campos y consultado la normativa de cada incidencia legal."
    ),
    parameters=_inline_refs(AgentReviewCandidate.model_json_schema()),
)


@dataclass(frozen=True)
class AgentRun:
    output: AgentReviewCandidate
    trace: list[TraceStep]
    usage: LLMUsage
    stop_reason: StopReason
    # Every fragment a search returned during the run: the only ones a finding may cite.
    fragments: dict[int, RegulationFragment] = field(default_factory=dict)


class ToolBox:
    """Runs the tools a model asks for. Shared by the hand-written loop and the graph of #41.

    Nothing the model asks for raises out of here: an unknown tool, malformed arguments or a tool
    that fails all become a `ToolResult` the model reads on its next turn.
    """

    def __init__(self, tools: list[Tool], *, role: AgentRole = AgentRole.REVIEWER) -> None:
        self._tools = {tool.spec.name: tool for tool in tools}
        self._role = role
        # The model is told only about the tools its role may call: least privilege starts there,
        # and the check in `execute` holds even when a model asks for one it was never shown.
        self.specs = [tool.spec for tool in tools if may_call(role, tool.spec.name)] + [SUBMIT_SPEC]

    async def execute(self, call: RequestedToolCall) -> tuple[ToolResult, int]:
        started = time.perf_counter()
        if not may_call(self._role, call.name):
            audit(self._role, call.name, AuditOutcome.DENIED, arguments=call.arguments)
            denied = ToolResult(ok=False, content=f"Llamada denegada: {call.name} no está permitida para este rol.")
            return denied, int((time.perf_counter() - started) * 1000)

        tool = self._tools.get(call.name)
        if call.malformed is not None:
            result = ToolResult(ok=False, content=MALFORMED_ARGUMENTS)
        elif tool is None:
            available = ", ".join(self._tools)
            result = ToolResult(ok=False, content=f"No existe la herramienta {call.name}. Disponibles: {available}.")
        else:
            try:
                result = await tool.run(call.arguments)
            except Exception as error:
                # A tool failing is information for the model, never a crash of the run.
                log.warning("agent.tool_failed", tool=call.name, exc_info=True)
                result = ToolResult(ok=False, content=TOOL_FAILED.format(error=type(error).__name__))
        latency_ms = int((time.perf_counter() - started) * 1000)
        audit(
            self._role,
            call.name,
            AuditOutcome.ALLOWED if result.ok else AuditOutcome.FAILED,
            arguments=call.arguments,
            latency_ms=latency_ms,
        )
        return result, latency_ms


class AgentLoop:
    def __init__(
        self,
        llm: ToolCallingLLM,
        tools: list[Tool],
        *,
        max_iterations: int = DEFAULT_MAX_ITERATIONS,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        prompt_version: str = "v3",
    ) -> None:
        self._llm = llm
        self._toolbox = ToolBox(tools)
        self._specs = self._toolbox.specs
        self._max_iterations = max_iterations
        self._timeout = timeout_seconds
        self._prompt_version = prompt_version

    async def run(self, listing: Listing, *, feedback: str | None = None) -> AgentRun:
        """One pass of the actor. `feedback` is what the critic rejected last time, quoted back."""
        system, user = render_agent_review_prompt(listing, version=self._prompt_version)
        if feedback:
            user = f"{user}\n\n{feedback}"
        messages: list[dict[str, Any]] = [{"role": "system", "content": system}, {"role": "user", "content": user}]
        trace: list[TraceStep] = []
        usages: list[LLMUsage] = []
        fragments: dict[int, RegulationFragment] = {}
        failures: dict[str, int] = {}
        deadline = time.monotonic() + self._timeout
        stop = StopReason.MAX_ITERATIONS

        for _ in range(self._max_iterations):
            if time.monotonic() > deadline:
                stop = StopReason.TIMEOUT
                break

            completion = await self._llm.complete_with_tools(messages=messages, tools=self._specs)
            usages.append(completion.usage)
            messages.append(completion.message)

            if not completion.tool_calls:
                trace.append(
                    TraceStep(step=len(trace) + 1, tool="(sin herramienta)", thought=completion.content, ok=False)
                )
                messages.append({"role": "user", "content": NUDGE_TO_SUBMIT})
                continue

            thought = completion.content
            for call in completion.tool_calls:
                if call.name == SUBMIT:
                    candidate, error = parse_submission(call)
                    trace.append(
                        TraceStep(
                            step=len(trace) + 1,
                            tool=SUBMIT,
                            ok=candidate is not None,
                            result="Revisión entregada" if candidate else error,
                            thought=thought,
                        )
                    )
                    if candidate is not None:
                        return self._finished(candidate, trace, usages, StopReason.COMPLETED, fragments)
                    messages.append(tool_message(call, error))
                    continue

                result, latency_ms = await self._toolbox.execute(call)
                if isinstance(result.data.get("fragments"), list):
                    fragments.update({fragment.chunk_id: fragment for fragment in result.data["fragments"]})
                trace.append(
                    TraceStep(
                        step=len(trace) + 1,
                        tool=call.name,
                        arguments=call.arguments,
                        result=result.content[:RESULT_PREVIEW_CHARS],
                        ok=result.ok,
                        latency_ms=latency_ms,
                        thought=thought,
                    )
                )
                thought = None
                messages.append(tool_message(call, result.content))

                if not result.ok:
                    key = f"{call.name}:{json.dumps(call.arguments, sort_keys=True)}"
                    failures[key] = failures.get(key, 0) + 1
                    if failures[key] >= 2:
                        stop = StopReason.TOOL_ERROR
            if stop == StopReason.TOOL_ERROR:
                break

        return await self._final_submission(messages, trace, usages, stop, fragments)

    async def _final_submission(
        self,
        messages: list[dict[str, Any]],
        trace: list[TraceStep],
        usages: list[LLMUsage],
        stop: StopReason,
        fragments: dict[int, RegulationFragment],
    ) -> AgentRun:
        """Out of steps, time or luck: one forced call to hand in what the model has."""
        log.warning("agent.forced_submission", stop_reason=stop, steps=len(trace))
        messages.append({"role": "user", "content": FINAL_CALL})
        completion = await self._llm.complete_with_tools(messages=messages, tools=[SUBMIT_SPEC], force_tool=SUBMIT)
        usages.append(completion.usage)

        for call in completion.tool_calls:
            if call.name == SUBMIT:
                candidate, error = parse_submission(call)
                trace.append(
                    TraceStep(
                        step=len(trace) + 1, tool=SUBMIT, ok=candidate is not None, result=error or "Revisión entregada"
                    )
                )
                if candidate is not None:
                    return self._finished(candidate, trace, usages, stop, fragments)
        raise ReviewGenerationError(f"the agent stopped ({stop}) without a valid review")

    @staticmethod
    def _finished(
        candidate: AgentReviewCandidate,
        trace: list[TraceStep],
        usages: list[LLMUsage],
        stop: StopReason,
        fragments: dict[int, RegulationFragment],
    ) -> AgentRun:
        usage = usages[0]
        for more in usages[1:]:
            usage = combined(usage, more)
        return AgentRun(output=candidate, trace=trace, usage=usage, stop_reason=stop, fragments=fragments)


def parse_submission(call: RequestedToolCall) -> tuple[AgentReviewCandidate | None, str]:
    if call.malformed is not None:
        return None, "La revisión no es JSON válido. Vuelve a entregarla."
    try:
        return AgentReviewCandidate.model_validate(call.arguments), ""
    except ValidationError as error:
        problems = "; ".join(f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in error.errors()[:5])
        return None, f"La revisión no cumple el esquema ({problems}). Corrígela y vuelve a entregarla."


def tool_message(call: RequestedToolCall, content: str) -> dict[str, Any]:
    return {"role": "tool", "tool_call_id": call.id, "content": content}
