import { useId, useState, type FormEvent } from "react";
import { ApiError, askRegulations, UNEXPECTED_ERROR } from "../api/client";
import type { Jurisdiction, RegulationAnswer, Usage } from "../api/types";
import { Feedback } from "./Feedback";
import { ServiceBanner } from "./ServiceBanner";

export const EMPTY_QUESTION = "La pregunta está vacía";
export const NO_MODEL_CALL = "Sin llamada al modelo: la normativa indexada no cubría la pregunta.";

const COST = new Intl.NumberFormat("es-ES", { minimumFractionDigits: 4, maximumFractionDigits: 4 });

function usageLine(usage: Usage): string {
  if (usage.attempts === 0) return NO_MODEL_CALL;
  const cost = usage.estimated_cost_usd === null ? "no disponible" : `${COST.format(Number(usage.estimated_cost_usd))} USD`;
  return `Modelo: ${usage.model} · ${usage.input_tokens} + ${usage.output_tokens} tokens · ${usage.latency_ms} ms · Coste estimado: ${cost}`;
}

/** What an answer was built from, one click away: when it looks wrong, that is the first question. */
function TechnicalDetails({ answer }: { answer: RegulationAnswer }) {
  return (
    <details className="rounded-xl border border-line bg-canvas p-4 text-sm">
      <summary className="cursor-pointer font-medium text-ink-soft">Detalles técnicos</summary>
      <div className="mt-3 space-y-3">
        {answer.retrieved.length === 0 ? (
          <p className="text-muted">La búsqueda no ha devuelto ningún fragmento por encima del umbral.</p>
        ) : (
          <table className="w-full text-left">
            <caption className="mb-2 text-left text-muted">Fragmentos recuperados</caption>
            <thead className="text-xs text-muted">
              <tr>
                <th className="py-1 pr-3 font-medium">Puntuación</th>
                <th className="py-1 pr-3 font-medium">Artículo</th>
                <th className="py-1 font-medium">Norma</th>
              </tr>
            </thead>
            <tbody>
              {answer.retrieved.map((chunk) => (
                <tr key={chunk.chunk_id} className="border-t border-line">
                  <td className="py-1 pr-3 tabular-nums">{chunk.score.toFixed(3)}</td>
                  <td className="py-1 pr-3">{chunk.article_title}</td>
                  <td className="py-1">{chunk.law_id}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        <p className="text-xs text-muted">{usageLine(answer.usage)}</p>
      </div>
    </details>
  );
}

function Answer({ answer }: { answer: RegulationAnswer }) {
  return (
    <div className="space-y-4">
      {answer.has_answer ? (
        <div className="space-y-3 rounded-xl border border-line bg-canvas p-4">
          <p className="leading-relaxed whitespace-pre-line">{answer.answer}</p>
          <div>
            <h3 className="text-sm font-semibold">Fuentes</h3>
            <ul className="mt-2 space-y-1 text-sm">
              {answer.citations.map((citation) => (
                <li key={citation.chunk_id}>
                  <a
                    href={citation.url}
                    target="_blank"
                    rel="noreferrer"
                    className="text-accent-strong underline-offset-2 hover:underline"
                  >
                    {citation.law_title.replace(/\.$/, "")} · {citation.article}
                  </a>
                </li>
              ))}
            </ul>
          </div>
        </div>
      ) : (
        <p role="note" className="rounded-xl bg-warn-soft p-4 leading-relaxed text-warn">
          {answer.answer}
        </p>
      )}
      <p className="text-xs text-muted">No es asesoramiento legal.</p>
      <TechnicalDetails answer={answer} />
      <Feedback key={answer.request_id} kind="regulation_answer" requestId={answer.request_id} />
    </div>
  );
}

type RegulationQuestionProps = {
  // Null searches every law in the corpus.
  jurisdictions: Jurisdiction[] | null;
  suggestions: string[];
  placeholder?: string;
};

/** A question to the regulation Q&A, answered only from the BOE and citing the article it comes from. */
export function RegulationQuestion({ jurisdictions, suggestions, placeholder }: RegulationQuestionProps) {
  const fieldId = useId();
  const [question, setQuestion] = useState("");
  const [asking, setAsking] = useState(false);
  const [answer, setAnswer] = useState<RegulationAnswer | null>(null);
  const [error, setError] = useState<string | null>(null);

  const ask = async (text: string) => {
    const trimmed = text.trim();
    if (!trimmed) {
      setError(EMPTY_QUESTION);
      return;
    }
    setAsking(true);
    setError(null);
    try {
      setAnswer(await askRegulations(trimmed, jurisdictions));
    } catch (failure) {
      setAnswer(null);
      setError(failure instanceof ApiError ? failure.message : UNEXPECTED_ERROR);
    } finally {
      setAsking(false);
    }
  };

  const submit = (event: FormEvent) => {
    event.preventDefault();
    void ask(question);
  };

  const suggest = (text: string) => {
    setQuestion(text);
    void ask(text);
  };

  return (
    <div className="space-y-4">
      <ServiceBanner />
      <form onSubmit={submit} className="space-y-3">
        <label className="block text-sm font-medium" htmlFor={fieldId}>
          Tu pregunta
        </label>
        <textarea
          id={fieldId}
          value={question}
          onChange={(event) => setQuestion(event.target.value)}
          rows={3}
          maxLength={1000}
          placeholder={placeholder}
          className="w-full rounded-xl border border-line bg-canvas px-4 py-3 placeholder:text-muted"
        />
        {suggestions.length > 0 && (
          <div className="space-y-2">
            <p className="text-xs text-muted">O prueba con una de estas:</p>
            <ul className="flex flex-wrap gap-2">
              {suggestions.map((suggestion) => (
                <li key={suggestion}>
                  <button
                    type="button"
                    disabled={asking}
                    onClick={() => suggest(suggestion)}
                    className="rounded-full border border-line bg-canvas px-3 py-1.5 text-left text-sm text-ink-soft hover:border-ink-soft hover:text-ink disabled:opacity-50"
                  >
                    {suggestion}
                  </button>
                </li>
              ))}
            </ul>
          </div>
        )}
        <button
          type="submit"
          disabled={asking}
          className="rounded-lg bg-ink px-5 py-2.5 text-sm font-medium text-white hover:bg-ink-soft disabled:opacity-60"
        >
          {asking ? "Buscando en la normativa..." : "Preguntar"}
        </button>
      </form>
      <div aria-live="polite" className="space-y-4">
        {error && (
          <p role="alert" className="rounded-xl bg-danger-soft px-4 py-3 text-sm text-danger">
            {error}
          </p>
        )}
        {answer && <Answer answer={answer} />}
      </div>
    </div>
  );
}
