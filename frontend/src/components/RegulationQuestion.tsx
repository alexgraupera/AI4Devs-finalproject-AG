import { useId, useState, type FormEvent } from "react";
import { ApiError, askRegulations, UNEXPECTED_ERROR } from "../api/client";
import type { Jurisdiction, RegulationAnswer } from "../api/types";
import { Sources, TechnicalDetails } from "./AnswerParts";
import { Feedback } from "./Feedback";
import { ServiceBanner } from "./ServiceBanner";

export const EMPTY_QUESTION = "La pregunta está vacía";

function Answer({ answer }: { answer: RegulationAnswer }) {
  return (
    <div className="space-y-4">
      {answer.has_answer ? (
        <div className="space-y-3 rounded-xl border border-line bg-canvas p-4">
          <p className="leading-relaxed whitespace-pre-line">{answer.answer}</p>
          <Sources citations={answer.citations} />
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
