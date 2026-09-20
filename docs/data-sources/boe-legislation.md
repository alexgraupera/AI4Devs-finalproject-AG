# BOE consolidated legislation

Official consolidated (in force) text of Spanish laws, from the BOE open data API. It is the **RAG corpus** of the project.

- **Documentation**: [BOE open data: consolidated legislation API](https://www.boe.es/datosabiertos/api/api.php)
- **Licence**: BOE open data, reusable citing the source.
- **Auth**: none.
- **Example**: [`examples/boe_consolidated_law.py`](examples/boe_consolidated_law.py)

## Laws in the corpus

| Id | Law | Why | Consolidated update (at validation) |
|---|---|---|---|
| `BOE-A-1994-26003` | Ley 29/1994 de Arrendamientos Urbanos (LAU) | Rental contracts: deposit, expenses, duration, rent updates | 2026-04-30 |
| `BOE-A-2023-12203` | Ley 12/2023 por el derecho a la vivienda | Minimum information for tenants, stressed areas | 2026-08-03 |
| `BOE-A-2021-9176` | Real Decreto 390/2021, energy performance certificate | Energy label in every listing | 2026-07-23 |
| `BOE-A-2008-3657` | Ley 18/2007, del derecho a la vivienda (Cataluña) | Regional duties on a rental offer: art. 61 requires giving sufficient information on the essential conditions before taking any payment on account | 2026-07-13 |

> Regional laws live in this same API (`ambito` is `Autonómico` instead of `Estatal`) and have
> the same block structure, so **one parser serves both**. What changes is the jurisdiction the
> chunks are tagged with, which is what lets a query be restricted to, or contrasted between,
> state and regional rules.

Articles checked during the validation (they support the listing checklist):

| Article | Content | Block id |
|---|---|---|
| LAU art. 36 | Deposit of one monthly rent for housing | `a36` |
| Ley 18/2007 art. 61 | Information required in a rental offer, before any payment on account | `a61` |
| LAU art. 20.1 | Real estate management and contract formalisation costs are paid by the landlord | `a20` |
| Ley 12/2023 art. 31 | Minimum information available to people interested in buying or renting | `a3-3` |
| RD 390/2021 art. 15.2 | The energy label must be included in every offer and advertisement for sale or rent | `a1-7` |

## Endpoints

Base: `https://www.boe.es/datosabiertos/api/legislacion-consolidada/id/{law_id}`

| Endpoint | Returns | Formats |
|---|---|---|
| `/metadatos` | Title, dates, repeal status, ELI and HTML URLs | XML, JSON |
| `/texto` | Full text: every block with every historical version | XML only |
| `/texto/indice` | List of blocks (id, title, last update, URL) | XML only |
| `/texto/bloque/{block_id}` | One block (e.g. `a36`) with its versions | XML only |

> ⚠️ The text endpoints answer HTTP 400 (`No soportado ningún mime type de la cabecera Accept`) to `Accept: application/json`. Always send `Accept: application/xml`.

### Metadata

```bash
curl -H "Accept: application/json" \
  https://www.boe.es/datosabiertos/api/legislacion-consolidada/id/BOE-A-1994-26003/metadatos
```

Relevant fields (XML version of the real response):

```xml
<metadatos>
  <fecha_actualizacion>20260430T073359Z</fecha_actualizacion>
  <identificador>BOE-A-1994-26003</identificador>
  <rango codigo="1300">Ley</rango>
  <titulo>Ley 29/1994, de 24 de noviembre, de Arrendamientos Urbanos.</titulo>
  <fecha_vigencia>19950101</fecha_vigencia>
  <estatus_derogacion>N</estatus_derogacion>
  <vigencia_agotada>N</vigencia_agotada>
  <url_eli>https://www.boe.es/eli/es/l/1994/11/24/29</url_eli>
  <url_html_consolidada>https://www.boe.es/buscar/act.php?id=BOE-A-1994-26003</url_html_consolidada>
</metadatos>
```

Use `fecha_actualizacion` to decide whether a law must be re-ingested, and `estatus_derogacion` / `vigencia_agotada` to discard repealed laws.

### Full text

```bash
curl -H "Accept: application/xml" \
  https://www.boe.es/datosabiertos/api/legislacion-consolidada/id/BOE-A-1994-26003/texto
```

Structure (real response, trimmed):

```xml
<response>
  <status><code>200</code><text>ok</text></status>
  <data>
    <texto>
      <bloque id="preambulo" tipo="preambulo">...</bloque>
      <bloque id="ti" tipo="encabezado" titulo="TÍTULO I">...</bloque>
      <bloque id="a36" tipo="precepto" titulo="Artículo 36">
        <version id_norma="BOE-A-1994-26003" fecha_publicacion="19941125" fecha_vigencia="19950101">
          <p class="articulo">Artículo 36. Fianza.</p>
          <p class="parrafo">1. A la celebración del contrato será obligatoria la exigencia y prestación de fianza ...</p>
        </version>
        <!-- ... 5 more versions ... -->
        <version id_norma="BOE-A-2019-3108" fecha_publicacion="20190305" fecha_vigencia="20190306">
          <p class="articulo">Artículo 36. Fianza.</p>
          <p class="parrafo">1. A la celebración del contrato será obligatoria la exigencia y prestación de fianza en metálico en cantidad equivalente a una mensualidad de renta en el arrendamiento de viviendas ...</p>
          <p class="parrafo">2. Durante los cinco primeros años de duración del contrato, o durante los siete primeros años si el arrendador fuese persona jurídica, ...</p>
        </version>
      </bloque>
    </texto>
  </data>
</response>
```

- `bloque@tipo`: `precepto` for articles and provisions; `preambulo`, `encabezado` (titles, chapters)... are not articles.
- `version@id_norma`: the norm that introduced that wording (useful to cite "amended by").
- `version@fecha_vigencia`: date the wording came into force.

### Citation links

The consolidated HTML page has anchors with the block id, so a citation link is:

```
https://www.boe.es/buscar/act.php?id={law_id}#{block_id}
```

e.g. <https://www.boe.es/buscar/act.php?id=BOE-A-2023-12203#a3-3> (Ley 12/2023, article 31).

## Python usage

From [`examples/boe_consolidated_law.py`](examples/boe_consolidated_law.py):

```python
def normalize(text: str) -> str:
    # The BOE mixes regular and non-breaking spaces ("Artículo\xa031"): collapse every whitespace.
    return " ".join(text.split())


def version_in_force(block: ET.Element, today: str) -> ET.Element | None:
    # A block keeps every historical version. Pick the latest one already in force.
    versions = [v for v in block.findall("version") if v.get("fecha_vigencia", "") <= today]
    return max(versions, key=lambda v: v.get("fecha_vigencia", ""), default=None)


def fetch_articles(law_id: str) -> list[Article]:
    response = httpx.get(API.format(law_id=law_id) + "/texto", headers={"Accept": "application/xml"}, timeout=60)
    response.raise_for_status()
    root = ET.fromstring(response.content)
    ...
    for block in root.iter("bloque"):
        if block.get("tipo") != "precepto":
            continue
        version = version_in_force(block, today)
        paragraphs = [normalize("".join(p.itertext())) for p in version.findall("p")]
        ...
```

Output:

```
$ uv run docs/data-sources/examples/boe_consolidated_law.py
Ley 29/1994, de 24 de noviembre, de Arrendamientos Urbanos. (updated 20260430T073359Z, repealed: N)
64 articles in force, 103,813 characters

[a36] Artículo 36 · in force since 20190306 (BOE-A-2019-3108)
https://www.boe.es/buscar/act.php?id=BOE-A-1994-26003#a36
Artículo 36. Fianza.
1. A la celebración del contrato será obligatoria la exigencia y prestación de fianza en metálico ...
```

## Size and chunking

Measured with `make corpus-report` on 2026-09-20, over the articles **in force** (`precepto`
blocks only):

| Law | Articles in force | Characters | p50 | p95 | Longest |
|---|---|---|---|---|---|
| LAU | 64 | 103,813 | 821 | 3,996 | 14,939 (`dtsegunda`) |
| Ley 12/2023 | 56 | 105,288 | 1,410 | 6,535 | 8,023 (`a3`) |
| RD 390/2021 | 44 | 105,401 | 1,175 | 8,029 | 13,446 (`ai-6`) |
| Ley 18/2007 (Cataluña) | 189 | 298,769 | 1,190 | 3,764 | 8,051 (`a3`) |

With the stressed-areas resolutions the corpus is **364 items and ~617k characters** (roughly
150k tokens). The Catalan law alone is about half of it.

- Most articles are a few thousand characters: **one chunk per article** keeps citations exact.
- The ~60k-character blocks are **preambles**, not articles (LAU 21k, Ley 18/2007 39k), and the
  parser leaves them out: they are legislative justification, not rules to cite. The longest
  actual article is 15k characters (LAU `dtsegunda`, a transitional provision), and p95 sits
  between 3.7k and 8k, so paragraph splitting affects a handful of blocks rather than many.
- Keep as chunk metadata: `law_id`, law title, `block_id`, article title, `fecha_vigencia`, `id_norma` and the citation URL.

## Gotchas

- Text endpoints: `Accept: application/xml` only.
- Block ids are not article numbers: read the number from `titulo`.
- Normalize whitespace (non-breaking spaces) in titles and text.
- Pick the version in force, not simply the last one, in case a future wording is already published.
