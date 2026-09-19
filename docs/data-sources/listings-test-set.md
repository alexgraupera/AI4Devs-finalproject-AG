# Rental listings for the evals test set

The evaluation suite needs rental listings annotated with their known defects. No public dataset of Spanish rental listing texts is available, so the test set is **built on top of the real sources** of the project.

## Sources considered

| Source | Result |
|---|---|
| [`idealista18`](https://github.com/paezha/idealista18) (ODbL) | Discarded: only **sale** listings from 2018 (Madrid, Barcelona, Valencia), structured fields only, no description text. |
| Scraping real estate portals | Discarded: against their terms of use. |
| Idealista API | Discarded: requires an approved partner access. |
| Company data (marketplace) | Out of scope: the project only uses public data. |

## Approach

Each test listing combines real data with a description written for the test set:

| Part | Source |
|---|---|
| Property (address, surface, year, use) | Real property from the [Catastro](catastro.md) |
| Price | Inside or deliberately outside the real [SERPAVI](serpavi.md) range of its municipality |
| Description and conditions | Written for the test set, following common listing patterns |
| Expected defects | Annotated against the real regulation in the [BOE](boe-legislation.md) |

Example of an annotated listing:

```json
{
  "id": "madrid-quesada-11-defects-01",
  "listing": {
    "title": "Piso reformado en Chamberí",
    "description": "Piso exterior de 2 habitaciones, totalmente reformado. Fianza de 2 meses y honorarios de agencia a cargo del inquilino.",
    "price_eur_month": 1400,
    "usable_surface_m2": 58,
    "municipality": "Madrid",
    "cadastral_reference": "0663903VK4706D0004FX",
    "energy_rating": null
  },
  "expected_findings": [
    {"category": "energy_label", "severity": "high", "source": "BOE-A-2021-9176#a1-7"},
    {"category": "deposit", "severity": "high", "source": "BOE-A-1994-26003#a36"},
    {"category": "agency_fees", "severity": "high", "source": "BOE-A-1994-26003#a20"},
    {"category": "price_above_market_range", "severity": "info", "source": "SERPAVI 2024 Madrid P75 17.92 EUR/m2"}
  ]
}
```

In this example:
- The price (1,400 €/month for 62 m² built) is above the Madrid P75 for that surface (1,111 €/month).
- The deposit of two months breaks LAU art. 36.
- Agency fees charged to the tenant break LAU art. 20.1.
- The listing has no energy label (RD 390/2021 art. 15.2).

## Rules

- No personal data: no owner names, phone numbers or emails.
- Every expected finding cites its source (BOE block or SERPAVI figure), so the evaluation can also check citation accuracy.
- Include clean listings (no defects) to measure false positives, and adversarial ones (prompt injection inside the description, non-listing text).
