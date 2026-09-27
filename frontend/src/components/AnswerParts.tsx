/** The pieces of a regulation answer, shared by the `/normativa` page and the listing assistant. */

import type { Citation, RegulationAnswer } from "../api/types";
import { formatUsage } from "./format";

export const NO_MODEL_CALL = "Sin llamada al modelo: la normativa indexada no cubría la pregunta.";

/** Every article the answer rests on, as a link to the BOE: the reader checks, never takes it on trust. */
export function Sources({ citations }: { citations: Citation[] }) {
  return (
    <div>
      <h3 className="text-sm font-semibold">Fuentes</h3>
      <ul className="mt-2 space-y-1 text-sm">
        {citations.map((citation) => (
          <li key={citation.chunk_id}>
            <a href={citation.url} target="_blank" rel="noreferrer" className="text-accent-strong underline-offset-2 hover:underline">
              {citation.law_title.replace(/\.$/, "")} · {citation.article}
            </a>
          </li>
        ))}
      </ul>
    </div>
  );
}

/** What an answer was built from, one click away: when it looks wrong, that is the first question. */
export function TechnicalDetails({ answer }: { answer: RegulationAnswer }) {
  return (
    <details className="rounded-xl border border-line bg-canvas p-4 text-sm">
      <summary className="cursor-pointer font-medium text-ink-soft">Detalles técnicos</summary>
      <div className="mt-3 space-y-3 overflow-x-auto">
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
        <p className="text-xs text-muted">{answer.usage.attempts === 0 ? NO_MODEL_CALL : formatUsage(answer.usage)}</p>
      </div>
    </details>
  );
}
