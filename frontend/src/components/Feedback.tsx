import { useState } from "react";
import { ApiError, sendFeedback, UNEXPECTED_ERROR } from "../api/client";
import type { FeedbackKind } from "../api/types";

export const THANKS = "Gracias, lo usaremos para mejorar las revisiones.";

/**
 * The thumbs under every answer and review (#51): one vote per result, sent with the id of the
 * request that produced it, so a thumbs down leads to the log events of that request. Render it with
 * `key={requestId}`: a new result is a new vote.
 */
export function Feedback({ kind, requestId }: { kind: FeedbackKind; requestId: string | null }) {
  const [comment, setComment] = useState("");
  const [state, setState] = useState<"idle" | "sending" | "sent">("idle");
  const [error, setError] = useState<string | null>(null);

  if (!requestId) return null;

  if (state === "sent") {
    return (
      <p role="status" className="text-sm text-muted">
        {THANKS}
      </p>
    );
  }

  const vote = async (rating: "up" | "down") => {
    setState("sending");
    setError(null);
    try {
      await sendFeedback({ request_id: requestId, kind, rating, comment: comment.trim() || null });
      setState("sent");
    } catch (failure) {
      setError(failure instanceof ApiError ? failure.message : UNEXPECTED_ERROR);
      setState("idle");
    }
  };

  const buttonClass =
    "rounded-lg border border-line bg-canvas px-3 py-2 text-sm text-ink-soft transition-colors hover:border-ink-soft hover:text-ink disabled:opacity-50";

  return (
    <div className="space-y-2">
      <p className="text-sm font-medium text-ink-soft">¿Te ha servido?</p>
      {/* One row where there is room; where there is not (the assistant), the buttons go under the comment, together. */}
      <div className="flex flex-wrap gap-2">
        <label className="sr-only" htmlFor={`feedback-${requestId}`}>
          Comentario
        </label>
        <input
          id={`feedback-${requestId}`}
          value={comment}
          onChange={(event) => setComment(event.target.value)}
          maxLength={500}
          placeholder="¿Qué ha fallado? (opcional)"
          className="min-w-0 flex-[1_1_14rem] rounded-lg border border-line bg-canvas px-3 py-2 text-sm placeholder:text-muted"
        />
        <button type="button" disabled={state === "sending"} onClick={() => vote("up")} className={buttonClass}>
          👍 Útil
        </button>
        <button type="button" disabled={state === "sending"} onClick={() => vote("down")} className={buttonClass}>
          👎 No es correcto
        </button>
      </div>
      {error && (
        <p role="alert" className="text-sm text-danger">
          {error}
        </p>
      )}
    </div>
  );
}
