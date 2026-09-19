# Data sources

Public data sources used by the project. Every source was validated on 2026-09-19 with real requests before starting the implementation, and each guide below includes runnable examples. No source requires an API key, payment or registration.

| Source | Used for | Guide | Example | Status |
|---|---|---|---|---|
| BOE consolidated legislation | RAG corpus: rental regulations (LAU, Ley 12/2023, RD 390/2021) | [boe-legislation.md](boe-legislation.md) | [`boe_consolidated_law.py`](examples/boe_consolidated_law.py) | ✅ |
| BOE stressed areas resolutions | RAG corpus: declared stressed residential areas | [boe-stressed-areas.md](boe-stressed-areas.md) | [`boe_stressed_areas.py`](examples/boe_stressed_areas.py) | ✅ As text only |
| Catastro (OVC web services) | Agent tool: official property data | [catastro.md](catastro.md) | [`catastro.py`](examples/catastro.py) | ✅ |
| SERPAVI (Ministerio de Vivienda) | Agent tool: market rent range | [serpavi.md](serpavi.md) | [`serpavi.py`](examples/serpavi.py) | ✅ Market statistics, not the legal cap |
| Rental listings | Evals test set | [listings-test-set.md](listings-test-set.md) | - | ⚠️ No public dataset: built from the sources above |

## Running the examples

The examples are standalone scripts with inline dependencies ([PEP 723](https://peps.python.org/pep-0723/)), so they run without installing the project. From the repository root:

```bash
uv run docs/data-sources/examples/boe_consolidated_law.py                       # LAU, article 36
uv run docs/data-sources/examples/boe_consolidated_law.py BOE-A-2023-12203 "Artículo 31"
uv run docs/data-sources/examples/boe_stressed_areas.py                         # latest quarterly resolution
uv run docs/data-sources/examples/catastro.py                                   # residential building in Madrid
uv run docs/data-sources/examples/serpavi.py Valencia 85                        # market range for 85 m2
```

`serpavi.py` downloads a ~71 MB file into `data/raw/` (git-ignored) on its first run.

They are reference code: the project implementation should reuse their parsing rules and gotchas, adding caching, retries and tests.

## Decisions derived from the validation

- **RAG corpus**: the three consolidated laws plus the stressed areas resolutions, all from the BOE. ~115k tokens for the laws: embedding the whole corpus costs well under 0.01 USD.
- **Stressed areas** are not exposed as a deterministic tool: there is no consolidated machine-readable list and areas can be neighbourhoods or villages. The assistant cites the resolutions through RAG instead.
- **Rent price** is exposed as a *market range* (SERPAVI P25-P75), never as a legal verdict: the legal reference price is only available through the SERPAVI web calculator, which has no API.
- **Surface checks** against the Catastro need a tolerance: Catastro gives the built surface, listings usually give the usable one.
- **Listings for the evals** are written for the test set on top of real properties, prices and regulations (no personal data, following the repository policy).

## Common gotchas

| Source | Gotcha |
|---|---|
| BOE | Text endpoints only accept `Accept: application/xml` (JSON returns HTTP 400); metadata accepts JSON. |
| BOE | Block ids are not article numbers (Ley 12/2023 article 31 is block `a3-3`): read the number from `titulo`. |
| BOE | Titles and text mix non-breaking spaces (`"Artículo\xa031"`): normalize whitespace before comparing. |
| BOE | Every block keeps all its historical versions: pick the latest one whose `fecha_vigencia` is not in the future. |
| Catastro | Business errors come with HTTP 200 and a `lerr` list (e.g. code 16: no parcel at those coordinates). |
| Catastro | One match comes as `bico.bi`, several matches as `lrcdnp.rcdnp`. |
| SERPAVI | The ministry site answers HTTP 403 without a browser `User-Agent`. |
| SERPAVI | Suppressed values come as empty cells or empty strings (`""`). |
| SERPAVI | Municipality names are not unique (e.g. Cabanes in Castellón and Girona): key by INE code. |
