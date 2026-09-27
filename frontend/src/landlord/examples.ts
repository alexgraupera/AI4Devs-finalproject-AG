/**
 * Listings a landlord can start from, taken as they are from the annotated set the reviews are
 * evaluated on (`evals/datasets/listings.yaml`): what the review finds in each one is measured, not
 * hoped. The last two paused for a person in the agent run of 2026-09-26, so the moderation of a
 * later phase has cases to decide.
 */

import type { ListingInput } from "../api/types";

export type Example = {
  // The id of the listing in the evaluation set.
  id: string;
  label: string;
  input: ListingInput;
};

export const EXAMPLES: Example[] = [
  {
    id: "clean-valencia",
    label: "Anuncio correcto (Valencia)",
    input: {
      text: "Piso de 3 habitaciones y 2 baños en Ruzafa (Valencia), 90 m² útiles, con balcón y aire acondicionado. Alquiler de 1.200 € al mes con los gastos de comunidad incluidos; los suministros (luz, agua y gas) los paga el inquilino. Fianza de una mensualidad. Sin gastos de agencia para el inquilino. Certificado energético C.",
      price_eur_month: 1200,
      usable_surface_m2: 90,
      rooms: 3,
      municipality: "Valencia",
      energy_rating: "C",
    },
  },
  {
    id: "deposit-two-months",
    label: "Dos meses de fianza (Madrid)",
    input: {
      text: "Piso exterior de 2 habitaciones en Arganzuela (Madrid), 68 m² útiles, con ascensor. 1.100 € al mes con comunidad incluida; suministros aparte, a cargo del inquilino. Se piden dos meses de fianza. Sin gastos de agencia para el inquilino. Certificado energético D.",
      price_eur_month: 1100,
      usable_surface_m2: 68,
      rooms: 2,
      municipality: "Madrid",
      energy_rating: "D",
    },
  },
  {
    id: "fees-on-tenant",
    label: "Honorarios al inquilino (Málaga)",
    input: {
      text: "Piso de 3 habitaciones en el centro de Málaga, 85 m² útiles, reformado. 1.300 € al mes con comunidad incluida; suministros a cargo del inquilino. Fianza de una mensualidad. Los honorarios de la agencia, una mensualidad más IVA, corren a cargo del inquilino. Certificado energético E.",
      price_eur_month: 1300,
      usable_surface_m2: 85,
      rooms: 3,
      municipality: "Málaga",
      energy_rating: "E",
    },
  },
  {
    id: "madrid-three-violations",
    label: "Tres incumplimientos (Madrid)",
    input: {
      text: "Piso exterior de 2 habitaciones en Chamberí, 65 m² útiles, reformado, con ascensor y calefacción. 1.350 € al mes con comunidad incluida; suministros a cargo del inquilino. Se piden dos meses de fianza. Los gastos de agencia los paga el inquilino. Disponible ya.",
      price_eur_month: 1350,
      usable_surface_m2: 65,
      rooms: 2,
      municipality: "Madrid",
      energy_rating: null,
    },
  },
  {
    id: "girona-fees-and-offer",
    label: "Honorarios y oferta incompleta (Girona)",
    input: {
      text: "Piso de 2 habitaciones en el Barri Vell de Girona, 60 m² útiles, con vistas al río. 850 € al mes, comunidad incluida; suministros a cargo del inquilino. Fianza de una mensualidad. Honorarios de agencia a cargo del inquilino. Certificado energético E.",
      price_eur_month: 850,
      usable_surface_m2: 60,
      rooms: 2,
      municipality: "Girona",
      energy_rating: "E",
    },
  },
];
