# SERPAVI: rental price statistics

**Sistema Estatal de Referencia del Precio del Alquiler de Vivienda**, published by the Ministerio de Vivienda y Agenda Urbana from tax returns (rental income) matched with the Catastro. Used as an **agent tool** to compare the price of a listing with the **market range** of its municipality.

- **Page**: <https://www.mivau.gob.es/vivienda/alquila-bien-es-tu-derecho/serpavi>
- **Methodology**: [2026-03-18_Metodologia_SERPAVI.pdf](https://cdn.mivau.gob.es/portal-web-mivau/vivienda/serpavi/2026-03-18_Metodologia_SERPAVI.pdf)
- **Licence**: public statistics from the Ministry, reusable citing the source.
- **Auth**: none, but the site requires a browser `User-Agent`.
- **Example**: [`examples/serpavi.py`](examples/serpavi.py)

> ⚠️ This is a **statistical market range**, not the legal rent cap. The legal reference price for stressed areas is only available through the [SERPAVI web calculator](https://serpavi.mivau.gob.es/), which has no API. The assistant must present it as "market range", never as "illegal price".

## Download

```bash
curl -L -A "Mozilla/5.0" -o data/raw/serpavi_2011-2024.xlsx \
  "https://cdn.mivau.gob.es/portal-web-mivau/vivienda/serpavi/2026-03_09_bd_SERPAVI_2011-2024%20-%20DEFINITIVO%20WEB_v2.xlsx"
```

- ~71 MB `.xlsx`, edition 2011-2024 (published March 2026). Without a browser `User-Agent` the site answers HTTP 403.
- New editions change the file name: check the page for the latest link.
- Also available on the page: shapefiles of municipalities, districts and census sections (for point-in-polygon lookups).

## Workbook structure

| Sheet | Rows | Key columns |
|---|---|---|
| `Metadatos` | 41 | Field definitions |
| `CCAA` | 24 | `CCAA`, `LITCCAA` |
| `Provincias` | 52 | `CPRO`, `LITPRO` |
| `Municipios` | 8,894 | `CPRO`, `NPRO`, `CUMUN` (INE code), `NMUN` |
| `Distritos` | 10,542 | `CUMUN`, `LITMUN`, `CUDIS` |
| `Secciones censales` | 36,293 | `CUMUN`, `LITMUN`, `CUSEC` |

Measures are repeated per year with the suffix `_AA` (`_11` ... `_24`) and per housing type: `VC` (collective, i.e. flats) and `VU` (single-family). For flats use `VC`:

| Column (2024, flats) | Meaning |
|---|---|
| `BI_ALVHEPCO_TVC_24` | Rented properties in the sample |
| `ALQM2_LV_25_VC_24` / `_M_` / `_75_` | Monthly rent per m²: P25 / median / P75 |
| `ALQTBID12_25_VC_24` / `_M_` / `_75_` | Monthly rent per property: P25 / median / P75 |
| `SLVM2_25_VC_24` / `_M_` / `_75_` | Surface in m²: P25 / median / P75 |

## Coverage (2024, flats)

- **2,555 of 8,894 municipalities** have data: small municipalities are statistically suppressed.
- Examples (€/m² per month, P25 / median / P75):

| Municipality | INE | Sample | P25 | Median | P75 |
|---|---|---|---|---|---|
| Madrid | 28079 | 300,447 | 11.03 | 13.97 | 17.92 |
| Barcelona | 08019 | 140,872 | 11.11 | 13.68 | 16.77 |
| Valencia | 46250 | 65,742 | 6.14 | 8.18 | 10.85 |
| Sevilla | 41091 | 34,668 | 7.32 | 9.17 | 11.34 |

## Python usage

From [`examples/serpavi.py`](examples/serpavi.py):

```python
def _number(value: object) -> float | None:
    # Suppressed values come either as empty cells (None) or as empty strings ("").
    return None if value in (None, "") else float(value)


def load_municipalities(path: Path) -> dict[str, RentRange]:
    """Collective housing (VC) ranges of the last year, indexed by INE code (names are not unique: e.g. Cabanes)."""
    sheet = load_workbook(path, read_only=True)["Municipios"]
    rows = sheet.iter_rows(values_only=True)
    header = next(rows)
    col = {name: i for i, name in enumerate(header)}
    ...
```

Output:

```
$ uv run docs/data-sources/examples/serpavi.py
2555 municipalities with 2024 data
RentRange(municipality='Madrid', province='Madrid', ine_code='28079', year=2024, sample_size=300447, eur_m2_p25=11.03, eur_m2_median=13.97, eur_m2_p75=17.92)
Market range for 70 m2 in Madrid: 772 - 1,254 EUR/month (median 978)

$ uv run docs/data-sources/examples/serpavi.py Cabanes
2 municipalities named 'Cabanes': [RentRange(municipality='Cabanes', province='Castellón/Castelló', ine_code='12033', ...), RentRange(..., province='Girona', ine_code='17030', ...)]
```

Reading the workbook takes a few seconds: in the project, load the needed sheet once into PostgreSQL (e.g. a `rent_ranges` table keyed by INE code and year) instead of reading the Excel on every request.

## How the project uses it

- Tool input: municipality (INE code, or name + province) and surface.
- Output: P25-P75 range and median for that surface, with year and source.
- Combined with the Catastro, e.g. the 62 m² flat at Calle Quesada 11 (Madrid): 684 - 1,111 €/month market range, median 866 €/month.
- A listing clearly above P75 gets an informative finding ("above the market range of the municipality"), never a legal one.

## Gotchas

- Browser `User-Agent` required.
- Suppressed values: `None` or `""`.
- Municipality names are not unique (18 duplicated names, e.g. Cabanes): key by INE code (`CUMUN`).
- Catastro municipality codes are not INE codes: resolve the municipality by name and province, or by coordinates with the shapefiles.
- The latest data year lags about two years behind (2024 data published in 2026).
