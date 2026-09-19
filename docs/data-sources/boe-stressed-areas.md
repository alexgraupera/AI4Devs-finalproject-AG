# BOE stressed residential areas resolutions

Quarterly resolutions of the Secretaría de Estado de Vivienda y Agenda Urbana listing the **zonas de mercado residencial tensionado** declared in the previous quarter (Ley 12/2023, art. 18). They are part of the **RAG corpus**, so the assistant can cite whether an area has been declared as stressed.

- **Licence**: BOE open data, reusable citing the source.
- **Auth**: none.
- **Example**: [`examples/boe_stressed_areas.py`](examples/boe_stressed_areas.py)

## Known resolutions

| Id | Published | Quarter | Declarations |
|---|---|---|---|
| `BOE-A-2026-16532` | 2026-07-29 | Q2 2026 | 7 (Asturias areas, Santiago de Compostela, Basauri) |
| `BOE-A-2025-8636` | 2025-04-30 | Q1 2025 | 4 (Lasarte-Oria, Zumaia, Barakaldo, Irun) |

The full list of resolutions has to be gathered from the BOE search (title contains "zonas de mercado residencial tensionado") and from the [Ministry page](https://www.mivau.gob.es/vivienda/alquila-bien-es-tu-derecho/serpavi/consultar-zonas-de-mercado-residencial-tensionado). Catalonia's municipalities (271, declared in 2024) are listed in its own resolutions.

## Endpoint

These are daily BOE items (not consolidated legislation), so they use a different URL:

```bash
curl "https://www.boe.es/diario_boe/xml.php?id=BOE-A-2026-16532"
```

- `metadatos/titulo`, `metadatos/fecha_publicacion`: title and publication date.
- `texto/p`: paragraphs of the resolution.

## Content structure

Each resolution has, as paragraphs:

1. The list of declarations, one per paragraph starting with `– Resolución ...`, `– Orden ...`:

   ```
   – Orden de 28 de mayo de 2026, del consejero de Vivienda y Agenda Urbana, por la que se declara el municipio de Basauri como zona de mercado residencial tensionado, publicada en el «Boletín Oficial del País Vasco» el 8 de junio de 2026.
   ```

2. The same declarations repeated with their validity (three years) and links:

   ```
   – Declaración: Orden de 28 de mayo de 2026, ... (BOPV núm. 106, 8 de junio de 2026) https://www.euskadi.eus/...
   – Memoria: https://www.legegunea.euskadi.eus/.../Memoria-definitiva-ZT-Basauri.pdf.
   ```

## Python usage

From [`examples/boe_stressed_areas.py`](examples/boe_stressed_areas.py):

```python
response = httpx.get("https://www.boe.es/diario_boe/xml.php", params={"id": boe_id}, timeout=30)
root = ET.fromstring(response.content)
paragraphs = [" ".join("".join(p.itertext()).split()) for p in root.iter("p")]

declarations = [p.removeprefix("– ") for p in paragraphs if re.match(r"^– (Resolución|Orden|Decreto) ", p)]
```

Output:

```
$ uv run docs/data-sources/examples/boe_stressed_areas.py BOE-A-2025-8636
BOE-A-2025-8636 · published 20250430
Resolución de 29 de abril de 2025, de la Secretaría de Estado de Vivienda y Agenda Urbana, por la que se publica la relación de zonas de mercado residencial tensionado ...

4 declarations in this resolution:
 - el municipio de Lasarte-Oria
 - el municipio de Zumaia
 - el municipio de Barakaldo
 - el municipio de Irun
```

## Limitations and decision

- Each resolution only includes the declarations of its quarter: there is **no consolidated, machine-readable list**.
- Areas are free text and can be **smaller than a municipality**: "los ámbitos de La Arena y Cimadevilla, en el concejo de Gijón", "diversos ámbitos", specific villages of Llanes.
- Every declaration is valid for **three years**.

**Decision**: ingest the resolutions into the RAG corpus (one chunk per declaration, with its publication date and links) and let the assistant cite them. Do not build a deterministic "is this address in a stressed area" tool: it would be incomplete and could give wrong legal answers.
