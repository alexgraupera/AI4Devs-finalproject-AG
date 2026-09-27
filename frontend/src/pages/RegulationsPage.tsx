import { useState } from "react";
import type { Jurisdiction } from "../api/types";
import { RegulationQuestion } from "../components/RegulationQuestion";

const SCOPES: Record<string, Jurisdiction[] | null> = {
  "Toda España": null,
  Estatal: ["state"],
  Cataluña: ["catalonia"],
};

const GENERAL_QUESTIONS = [
  "¿Cuál es la fianza legal en un alquiler de vivienda?",
  "¿Quién paga los gastos de gestión inmobiliaria y de formalización del contrato?",
  "¿Cuánto puede durar como mínimo un contrato de alquiler de vivienda?",
  "¿Qué es una zona de mercado residencial tensionado?",
];

/** The regulation Q&A on its own, for a question that does not start from a listing. */
export function RegulationsPage() {
  const [scope, setScope] = useState("Toda España");

  return (
    <div className="mx-auto grid w-full max-w-6xl gap-10 px-4 py-12 lg:grid-cols-[minmax(0,1fr)_320px]">
      <div className="min-w-0 space-y-6">
        <header className="space-y-3">
          <h1 className="text-4xl font-semibold tracking-tight">Pregunta a la normativa</h1>
          <p className="text-lg text-muted">
            Las respuestas salen únicamente de la normativa indexada del BOE y citan el artículo del que proceden. No es
            asesoramiento legal.
          </p>
        </header>
        <label className="flex w-fit flex-col gap-1 text-xs font-medium text-muted">
          Ámbito
          <select
            value={scope}
            onChange={(event) => setScope(event.target.value)}
            className="rounded-lg border border-line bg-canvas px-3 py-2 text-sm font-normal text-ink"
          >
            {Object.keys(SCOPES).map((name) => (
              <option key={name}>{name}</option>
            ))}
          </select>
        </label>
        <RegulationQuestion
          jurisdictions={SCOPES[scope]}
          suggestions={GENERAL_QUESTIONS}
          placeholder="¿Cuál es la fianza legal en un alquiler de vivienda?"
        />
      </div>

      <aside className="space-y-4 self-start rounded-2xl border border-line bg-canvas-soft p-5 text-sm text-ink-soft">
        <h2 className="text-base font-semibold text-ink">Qué normativa puedo consultar</h2>
        <ul className="list-disc space-y-2 pl-5">
          <li>
            <strong className="text-ink">Ley 29/1994, de Arrendamientos Urbanos:</strong> fianza, duración, prórrogas,
            actualización de la renta, gastos, incumplimientos.
          </li>
          <li>
            <strong className="text-ink">Ley 12/2023, por el derecho a la vivienda:</strong> información mínima al
            arrendatario, zonas de mercado residencial tensionado.
          </li>
          <li>
            <strong className="text-ink">Real Decreto 390/2021:</strong> certificado y etiqueta de eficiencia energética.
          </li>
          <li>
            <strong className="text-ink">Ley 18/2007, del derecho a la vivienda (Cataluña):</strong> oferta de alquiler,
            cédula de habitabilidad, registro de fianzas.
          </li>
          <li>
            <strong className="text-ink">Resoluciones de zonas tensionadas</strong> publicadas en el BOE.
          </li>
        </ul>
        <p>
          <strong className="text-ink">Fuera de alcance:</strong> fiscalidad del alquiler (IRPF), comunidades de
          propietarios, procedimientos judiciales de desahucio, seguros y normativa autonómica distinta de la catalana.
          Sobre eso el asistente dirá que no lo sabe, que es lo correcto.
        </p>
      </aside>
    </div>
  );
}
