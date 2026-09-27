import { useEffect, useId, useRef, useState, type FormEvent, type KeyboardEvent, type ReactNode } from "react";
import { ApiError, askRegulations, UNEXPECTED_ERROR } from "../api/client";
import type { RegulationAnswer } from "../api/types";
import type { RentalListing } from "../catalogue/catalogue";
import { jurisdictionsOf, suggestedQuestions } from "../regulations/questions";
import { Sources, TechnicalDetails } from "./AnswerParts";
import { Feedback } from "./Feedback";
import { ChatIcon, CloseIcon, DoorIcon, SendIcon } from "./icons";
import { ServiceBanner } from "./ServiceBanner";

export const ASSISTANT_LAUNCHER = "Pregunta tus derechos";
export const ASSISTANT_TITLE = "Asistente de Umbral";
export const ASSISTANT_GREETING =
  "Hola. Pregúntame por la fianza, los gastos o la información que te tienen que dar por este piso. Respondo solo con la normativa publicada en el BOE y te enlazo el artículo del que sale cada respuesta.";
// The API answers each question on its own (no conversational memory, see docs/scope.md): the
// assistant says so, rather than let a follow-up question count on a context it does not have.
export const ONE_QUESTION_AT_A_TIME = "Cada pregunta se responde por separado. No es asesoramiento legal.";

type Turn = {
  id: number;
  question: string;
  answer?: RegulationAnswer;
  error?: string;
};

function AssistantBubble({ children }: { children: ReactNode }) {
  return (
    <div className="flex items-start gap-2">
      <span className="mt-1 grid size-7 shrink-0 place-items-center rounded-lg bg-accent text-white">
        <DoorIcon className="size-4" />
      </span>
      <div className="min-w-0 flex-1 space-y-3 rounded-2xl rounded-tl-sm border border-line bg-canvas p-3 text-sm">{children}</div>
    </div>
  );
}

function TurnView({ turn }: { turn: Turn }) {
  return (
    <li data-turn className="space-y-3">
      <p className="ml-auto w-fit max-w-[85%] rounded-2xl rounded-br-sm bg-ink px-4 py-2 text-sm text-white">{turn.question}</p>
      {turn.error ? (
        <AssistantBubble>
          <p role="alert" className="text-danger">
            {turn.error}
          </p>
        </AssistantBubble>
      ) : turn.answer ? (
        <AssistantBubble>
          {turn.answer.has_answer ? (
            <>
              <p className="leading-relaxed whitespace-pre-line">{turn.answer.answer}</p>
              <Sources citations={turn.answer.citations} />
            </>
          ) : (
            <p role="note" className="rounded-xl bg-warn-soft p-3 leading-relaxed text-warn">
              {turn.answer.answer}
            </p>
          )}
          <TechnicalDetails answer={turn.answer} />
          <Feedback key={turn.answer.request_id} kind="regulation_answer" requestId={turn.answer.request_id} />
        </AssistantBubble>
      ) : (
        <AssistantBubble>
          <p role="status" className="text-muted">
            Buscando en la normativa...
          </p>
        </AssistantBubble>
      )}
    </li>
  );
}

/**
 * The regulation Q&A as the assistant of a listing: a button in the corner of the page that opens a
 * conversation. The questions are searched in the laws that apply to the listing, and the conversation
 * stays while the page is open, closed or not. Render it with `key={listing.id}`: another listing is
 * another conversation.
 */
export function ListingAssistant({ listing }: { listing: RentalListing }) {
  const titleId = useId();
  const [open, setOpen] = useState(false);
  const [question, setQuestion] = useState("");
  const [turns, setTurns] = useState<Turn[]>([]);
  const launcher = useRef<HTMLButtonElement>(null);
  const field = useRef<HTMLTextAreaElement>(null);
  const log = useRef<HTMLDivElement>(null);
  const wasOpen = useRef(false);

  const asking = turns.some((turn) => !turn.answer && !turn.error);
  const asked = new Set(turns.map((turn) => turn.question));
  const suggestions = suggestedQuestions(listing).filter((suggestion) => !asked.has(suggestion));

  // Opening puts the cursor in the question; closing gives the focus back to the button that opened it.
  useEffect(() => {
    if (open) field.current?.focus();
    else if (wasOpen.current) launcher.current?.focus();
    wasOpen.current = open;
  }, [open]);

  // The newest question at the top of the view, so its answer is read from the start, not from its end.
  useEffect(() => {
    const newest = log.current?.querySelector<HTMLElement>("li[data-turn]:last-of-type");
    if (log.current && newest) log.current.scrollTop = newest.offsetTop - 16;
  }, [turns, open]);

  const ask = async (text: string) => {
    const trimmed = text.trim();
    if (!trimmed || asking) return;
    const id = turns.length;
    setQuestion("");
    setTurns((current) => [...current, { id, question: trimmed }]);
    const settle = (result: Partial<Turn>) =>
      setTurns((current) => current.map((turn) => (turn.id === id ? { ...turn, ...result } : turn)));
    try {
      settle({ answer: await askRegulations(trimmed, jurisdictionsOf(listing)) });
    } catch (failure) {
      settle({ error: failure instanceof ApiError ? failure.message : UNEXPECTED_ERROR });
    }
  };

  const submit = (event: FormEvent) => {
    event.preventDefault();
    void ask(question);
  };

  // Enter sends, as in any chat; Shift+Enter writes a new line.
  const sendOnEnter = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      void ask(question);
    }
  };

  if (!open) {
    return (
      <button
        ref={launcher}
        type="button"
        aria-expanded={false}
        onClick={() => setOpen(true)}
        className="fixed right-4 bottom-4 z-40 flex items-center gap-2 rounded-full bg-ink px-5 py-3.5 text-sm font-medium text-white shadow-xl transition-transform hover:-translate-y-0.5 hover:bg-ink-soft"
      >
        <ChatIcon className="size-5" />
        {ASSISTANT_LAUNCHER}
      </button>
    );
  }

  return (
    <section
      role="dialog"
      aria-labelledby={titleId}
      onKeyDown={(event) => event.key === "Escape" && setOpen(false)}
      className="fixed inset-x-0 bottom-0 z-40 flex h-[85dvh] flex-col overflow-hidden rounded-t-3xl border border-line bg-canvas-soft shadow-2xl sm:inset-x-auto sm:right-4 sm:bottom-4 sm:h-[min(680px,calc(100dvh-2rem))] sm:w-[420px] sm:rounded-3xl"
    >
      <header className="flex items-start justify-between gap-3 bg-panel px-5 py-4 text-panel-text">
        <div>
          <h2 id={titleId} className="font-semibold">
            {ASSISTANT_TITLE}
          </h2>
          <p className="text-xs text-panel-muted">Tus derechos sobre este anuncio, con la normativa del BOE</p>
        </div>
        <button
          type="button"
          aria-label="Cerrar el asistente"
          onClick={() => setOpen(false)}
          className="grid size-8 shrink-0 place-items-center rounded-full text-panel-muted hover:bg-panel-raised hover:text-panel-text"
        >
          <CloseIcon className="size-5" />
        </button>
      </header>

      <div ref={log} role="log" aria-label="Conversación" className="relative flex-1 space-y-4 overflow-y-auto px-4 py-4">
        <ServiceBanner />
        <AssistantBubble>
          <p className="leading-relaxed">{ASSISTANT_GREETING}</p>
        </AssistantBubble>
        {turns.length > 0 && (
          <ol className="space-y-4">
            {turns.map((turn) => (
              <TurnView key={turn.id} turn={turn} />
            ))}
          </ol>
        )}
        {suggestions.length > 0 && (
          <div className="space-y-2 pl-9">
            <p className="text-xs text-muted">{turns.length === 0 ? "Puedes empezar por aquí:" : "También puedes preguntar:"}</p>
            <ul className="flex flex-col items-start gap-2">
              {suggestions.map((suggestion) => (
                <li key={suggestion}>
                  <button
                    type="button"
                    disabled={asking}
                    onClick={() => void ask(suggestion)}
                    className="rounded-2xl border border-accent-line bg-canvas px-3 py-1.5 text-left text-sm text-ink-soft hover:border-accent hover:text-ink disabled:opacity-50"
                  >
                    {suggestion}
                  </button>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>

      <form onSubmit={submit} className="border-t border-line bg-canvas p-3">
        <div className="flex items-end gap-2 rounded-2xl border border-line bg-canvas-soft p-2 focus-within:border-accent">
          <label htmlFor={`${titleId}-question`} className="sr-only">
            Tu pregunta
          </label>
          <textarea
            ref={field}
            id={`${titleId}-question`}
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
            onKeyDown={sendOnEnter}
            rows={2}
            maxLength={1000}
            placeholder="Escribe tu pregunta..."
            className="max-h-32 min-w-0 flex-1 resize-none bg-transparent px-2 py-1 text-sm outline-none placeholder:text-muted"
          />
          <button
            type="submit"
            aria-label="Preguntar"
            disabled={asking || !question.trim()}
            className="grid size-9 shrink-0 place-items-center rounded-xl bg-ink text-white hover:bg-ink-soft disabled:opacity-40"
          >
            <SendIcon className="size-5" />
          </button>
        </div>
        <p className="mt-2 px-1 text-[11px] text-muted">{ONE_QUESTION_AT_A_TIME}</p>
      </form>
    </section>
  );
}
