# Proyecto Final · Master AI Engineering (LIDR)

> README basado en la plantilla oficial [`AI4Devs-finalproject`](https://github.com/LIDR-academy/AI4Devs-finalproject). Las secciones marcadas con 🆕 se han añadido para cubrir los requisitos específicos del Proyecto Final de AI Engineering y de la Política de Gestión de Repositorios del programa.

## Índice

0. [Ficha del proyecto](#0-ficha-del-proyecto)
1. [Descripción general del producto](#1-descripción-general-del-producto)
2. [Arquitectura del sistema](#2-arquitectura-del-sistema)
3. [Modelo de datos](#3-modelo-de-datos)
4. [Especificación de la API](#4-especificación-de-la-api)
5. [Historias de usuario](#5-historias-de-usuario)
6. [Tickets de trabajo](#6-tickets-de-trabajo)
7. [Pull requests](#7-pull-requests)
8. 🆕 [Evaluación (evals)](#8--evaluación-evals)
9. 🆕 [Limitaciones conocidas y próximos pasos](#9--limitaciones-conocidas-y-próximos-pasos)

---

## 0. Ficha del proyecto

### **0.1. Tu nombre completo:**

Alex Graupera

### **0.2. Nombre del proyecto:**

### **0.3. Descripción breve del proyecto:**

### **0.4. URL del proyecto:**

> Puede ser pública o privada, en cuyo caso deberás compartir los accesos de manera segura. Puedes enviarlos a [alvaro@lidr.co](mailto:alvaro@lidr.co) usando algún servicio como [onetimesecret](https://onetimesecret.com/).

### 0.5. URL o archivo comprimido del repositorio

https://github.com/alexgraupera/AI4Devs-finalproject-AG (rama de entrega: `finalproject-AG`, tag: `v1.0-final-AG`)

> Puedes tenerlo alojado en público o en privado, en cuyo caso deberás compartir los accesos de manera segura. Puedes enviarlos a [alvaro@lidr.co](mailto:alvaro@lidr.co) usando algún servicio como [onetimesecret](https://onetimesecret.com/). También puedes compartir por correo un archivo zip con el contenido


---

## 1. Descripción general del producto

> Describe en detalle los siguientes aspectos del producto:

### **1.1. Objetivo:**

> Propósito del producto. Qué valor aporta, qué soluciona, y para quién.

### **1.2. Características y funcionalidades principales:**

> Enumera y describe las características y funcionalidades específicas que tiene el producto para satisfacer las necesidades identificadas.

### **1.3. Diseño y experiencia de usuario:**

> Proporciona imágenes y/o videotutorial mostrando la experiencia del usuario desde que aterriza en la aplicación, pasando por todas las funcionalidades principales.

### **1.4. Instrucciones de instalación:**
> Documenta de manera precisa las instrucciones para instalar y poner en marcha el proyecto en local (librerías, backend, frontend, servidor, base de datos, migraciones y semillas de datos, etc.)

**Requisitos:** [Docker](https://docs.docker.com/get-docker/) con Docker Compose. Para desarrollar sin Docker: [uv](https://docs.astral.sh/uv/) (instala Python 3.12 automáticamente) y `make`.

**Con Docker (recomendado):**

```bash
git clone https://github.com/alexgraupera/AI4Devs-finalproject-AG.git
cd AI4Devs-finalproject-AG
cp .env.example .env    # añade tus API keys cuando las fases que usan LLM lo requieran
make up                 # equivale a: docker compose up --build
```

- Interfaz (Streamlit): http://localhost:8501
- API (FastAPI): http://localhost:8000 · documentación OpenAPI en http://localhost:8000/docs
- Base de datos (PostgreSQL + pgvector): `localhost:5432`, usuario/contraseña/base `rental`

`make up` levanta también la base de datos del corpus y **aplica las migraciones al arrancar el
contenedor de la API**: no hay ningún paso manual, un contenedor que arranca es un contenedor
cuyo esquema corresponde al código que ejecuta. Puedes comprobarlo en `GET /health`, que
informa del estado del almacén (`ok`, `unavailable` o `disabled`).

**Sin Docker (desarrollo):**

```bash
make install   # uv sync
make api       # API con recarga automática en :8000
make ui        # en otra terminal: interfaz en :8501
make migrate   # aplica las migraciones (necesita DATABASE_URL)
make verify    # lint, formato, tipos y tests
```

**Construir el corpus normativo:**

```bash
make ingest          # descarga las seis fuentes del BOE, las escribe en pgvector y las embebe
make embed           # solo los embeddings pendientes (--force reembebe todo)
make corpus-report   # las descarga y valida, sin escribir nada
make corpus-drift    # ¿ha actualizado el BOE alguna norma desde la última ingesta?
```

`make ingest` necesita `DATABASE_URL` y las migraciones aplicadas. **Re-ejecutarlo es seguro**:
si el BOE no ha tocado una norma, no descarga su texto ni reescribe sus fragmentos. Medido sobre
el corpus real: la primera ejecución escribe 380 fragmentos en 1,5 s; la segunda no escribe nada
en 0,56 s.

Cuándo reingestar: cuando el BOE actualice una norma. Como eso pasa unas pocas veces al año y en
silencio, hay un workflow semanal
([`corpus-drift.yml`](.github/workflows/corpus-drift.yml)) que pide solo los metadatos (~5 KB),
los compara con [`corpus.lock.json`](corpus.lock.json) y **abre una issue** si alguna norma se ha
movido. Ejecutar `make ingest` y commitear el `corpus.lock.json` actualizado cierra el ciclo.

La base de datos es **opcional** mientras trabajas en la revisión de anuncios: sin
`DATABASE_URL` el servicio arranca igual y `/health` responde `"database": "disabled"`. Para
usarla en local, levanta solo la base con `docker compose up -d db` y exporta:

```bash
DATABASE_URL=postgresql+asyncpg://rental:rental@localhost:5432/rental
```

Los tests que necesitan una base de datos real (migraciones, repositorio y pipeline de ingesta)
se saltan salvo que exportes esa variable, así que `make verify` no depende de ningún servicio:

```bash
DATABASE_URL=postgresql+asyncpg://rental:rental@localhost:5432/rental uv run pytest
```

Ejecutarlos **no destruye tu corpus**: los de ingesta usan identificadores de prueba y los de
migraciones, que hacen `downgrade` y borran las tablas, corren contra una base aparte
(`rental_migrations`) que se crea sola.

---

## 2. Arquitectura del Sistema

### **2.1. Diagrama de arquitectura:**
> Usa el formato que consideres más adecuado para representar los componentes principales de la aplicación y las tecnologías utilizadas. Explica si sigue algún patrón predefinido, justifica por qué se ha elegido esta arquitectura, y destaca los beneficios principales que aportan al proyecto y justifican su uso, así como sacrificios o déficits que implica.


### **2.2. Descripción de componentes principales:**

> Describe los componentes más importantes, incluyendo la tecnología utilizada

> 🆕 Incluir cada capa de IA: CAG, pipeline RAG, capa de agentes, evaluación y despliegue.

### **2.3. Descripción de alto nivel del proyecto y estructura de ficheros**

> Representa la estructura del proyecto y explica brevemente el propósito de las carpetas principales, así como si obedece a algún patrón o arquitectura específica.

```
.
├── app/                      # Paquete de la aplicación, en capas
│   ├── main.py               # Factoría FastAPI (raíz de composición)
│   ├── config.py             # Configuración a partir de variables de entorno
│   ├── foundation/           # Plomería sin opinión de arquitectura IA (llm, prompts, guardrails…)
│   ├── domain/               # Contrato (schemas) y servicio conductor
│   ├── generation/           # Arquitecturas de IA: cag/ (cachés), rag/, agentic/
│   ├── ingestion/            # Corpus del BOE: descarga, validación, troceo y escritura
│   └── api/                  # Routers finos (transporte)
├── streamlit_app.py          # Cliente Streamlit: portada y estado de la API
├── pages/                    # Páginas del cliente (revisión de anuncios, consulta de normativa)
├── migrations/               # Migraciones Alembic: el esquema del corpus, revisado como código
├── alembic.ini               # Configuración de Alembic (la URL sale de DATABASE_URL, no de aquí)
├── tests/                    # Tests, con la misma estructura que el paquete
├── docs/
│   ├── data-sources/         # Guías y ejemplos ejecutables de las fuentes de datos públicas
│   └── decisions/            # Registro de decisiones de arquitectura (ADR)
├── Dockerfile                # Imagen única para la API y la interfaz
├── docker-compose.yml        # Servicios api (:8000), ui (:8501), cache (Redis) y db (pgvector)
├── benchmarks/retrieval/     # Set dorado de preguntas y métricas de recuperación
├── corpus.lock.json          # Versiones del BOE con las que se construyó el corpus
├── Makefile                  # Comandos de desarrollo y verificación
└── .github/workflows/        # CI en cada pull request y detección semanal de deriva del BOE
```

La aplicación separa la interfaz (Streamlit) del servicio de IA (FastAPI): la interfaz solo consume la API por HTTP, de modo que la lógica de IA se puede probar, desplegar y reutilizar de forma independiente.

El paquete `app/` está organizado en capas por responsabilidad: `foundation/` (plomería: LLM, prompts, guardrails, observabilidad), `domain/` (el contrato y el servicio conductor), `generation/` (las arquitecturas de IA: CAG, RAG y agentes) y `api/` (transporte). Cada capa solo importa de las que tiene por encima, y la regla clave es que las arquitecturas de `generation/` no se conocen entre sí: **solo componen a través del conductor**. Eso es lo que evita que el proyecto degenere en carpetas acopladas según se van apilando. Decisión detallada en [ADR 0001](docs/decisions/0001-stack-and-project-structure.md).

### **2.4. Infraestructura y despliegue**

> Detalla la infraestructura del proyecto, incluyendo un diagrama en el formato que creas conveniente, y explica el proceso de despliegue que se sigue

### **2.5. Seguridad**

**Guardrails de entrada.** Antes de gastar un solo token, el texto pasa cuatro capas, de la más barata a la más cara ([ADR 0004](docs/decisions/0004-guardrails.md)):

| Capa | Qué rechaza | Coste |
|---|---|---|
| Tamaño | Vacío, menos de 50 caracteres, más de 5.000 | 0 |
| Inyección de prompt | Patrones conocidos en español e inglés | 0 |
| Datos personales | Emails, teléfonos e IBAN | 0 |
| Moderación | Contenido de odio, violento o sexual | Llamada de red |

Ninguna capa corrige el texto: todas rechazan y explican el motivo, porque quitar en silencio un email publicaría un anuncio que su autor no escribió. Un rechazo local tarda unos 4 ms.

**Defensa en profundidad contra la inyección de prompt.** Las expresiones regulares son un primer corte que siempre será incompleto. La defensa real es el prompt `v2`: el anuncio llega entre etiquetas `<anuncio>` y el prompt declara que todo lo que hay dentro son datos que revisar, nunca instrucciones que obedecer, y que una instrucción encontrada ahí es una incidencia de calidad más. Probado contra la API real con una inyección que las regex no detectan: el sistema revisó el anuncio con normalidad y además señaló el intento.

**Gestión de secretos.** Las claves solo llegan por variables de entorno. El fichero `.env` está en `.gitignore` y `.env.example` documenta las variables necesarias, sin valores.

**Pendiente** (#5): token de servicio para todo el API, claves por router en los endpoints caros y límite de peticiones.

### **2.6. Tests**

> Describe brevemente algunos de los tests realizados

### **2.7. 🆕 Arquitectura de IA: CAG → RAG → agentes**

El sistema apila tres arquitecturas que **no se conocen entre sí**: solo componen en el servicio conductor (`app/domain/listing_review_service.py`). Hoy está construida la primera.

**Generación con conocimiento en el prompt (implementado)**

El conocimiento de la revisión es un checklist corto y estable: cinco puntos normativos, cada uno con el artículo que lo respalda, más criterios de calidad del anuncio. Vive en el prompt de sistema, versionado en `app/foundation/prompts/listing_review/v1/`, y no en el código ni en una base de datos. El flujo de una revisión es:

```
POST /api/v1/listings/review
  └→ app/api/listings.py                          (transporte: sin lógica de negocio)
       └→ app/domain/listing_review_service.py    (conductor)
            1. app/foundation/guardrails/input.py (tamaño, inyección, PII, moderación)
            2. app/foundation/prompts/loader.py   (plantillas Jinja2 versionadas)
            3. app/generation/cag/exact.py        (acierto exacto SHA-256; si acierta, termina aquí)
            4. app/foundation/llm/wrapper.py      (Router con fallback + Instructor)
            5. app/foundation/guardrails/output.py (descarta citas fuera del checklist)
            6. cache.set()                        (guarda la revisión)
```

La salida es un objeto `ListingReview` validado: una lista de incidencias con categoría, gravedad, mensaje, sugerencia y base legal, más un veredicto y un resumen. Si el modelo no devuelve algo que encaje en el esquema, Instructor se lo vuelve a pedir; no llega texto libre a la interfaz.

El acceso al modelo pasa siempre por `LLMWrapper`, el único módulo que importa `litellm`. Por eso el modelo es configuración (`LLM_MODEL=anthropic/claude-haiku-4-5`) y los tests sustituyen el LLM sin tocar la red. Decisiones en [ADR 0002](docs/decisions/0002-prompt-strategy-and-checklist.md), [ADR 0003](docs/decisions/0003-review-output-schema.md) y [ADR 0006](docs/decisions/0006-llm-wrapper-litellm-instructor.md).

**Caché exacta (implementada)**

Antes de preguntar al modelo, el conductor busca la revisión en caché. La clave es un SHA-256 de **los prompts completos** más el modelo y la versión del prompt, no del texto del anuncio: así, cambiar el checklist, subir la versión del prompt o cambiar de modelo invalida la caché por construcción, sin vaciados manuales.

Medido con la misma revisión repetida:

| | Primera petición | Segunda petición |
|---|---|---|
| Latencia | 5.672 ms | **1 ms** |
| Tokens | 2.340 + 635 | 0 |
| Coste | 0,0055 $ | **0 $** |

Un acierto se marca como tal (`cached: true`, proveedor `cache`) en vez de volver a imputar el coste original. Si Redis falla, se trata como fallo de caché y la revisión sigue: la caché es una optimización, no una dependencia. Sin `REDIS_URL` el sistema funciona igual, sin caché. Detalles en [ADR 0007](docs/decisions/0007-exact-match-cache.md).

**Caché semántica (pendiente)**: acierto por similitud para los casos en que el mismo piso se describe con otras palabras.

**RAG — corpus ingestado (en construcción)**

El checklist del prompt cubre lo que siempre hay que comprobar; el RAG cubre lo que hay que consultar. La primera mitad ya está: el corpus del BOE vive en la base de datos, troceado y listo para embeber.

```
make ingest
  └→ app/ingestion/boe/            (descarga y parseo: solo bloques en vigor)
       └→ app/ingestion/validation.py  (descarta lo inservible, cuenta el porqué)
            └→ app/ingestion/chunking.py (un fragmento por artículo)
                 └→ app/ingestion/repository.py (escribe solo lo que cambió)
```

| Fuente | Ámbito | Artículos | Fragmentos |
|---|---|---:|---:|
| Ley 29/1994 (LAU) | estatal | 64 | 68 |
| Ley 12/2023, derecho a la vivienda | estatal | 56 | 59 |
| RD 390/2021, certificado energético | estatal | 44 | 50 |
| Ley 18/2007, derecho a la vivienda | Cataluña | 189 | 192 |
| Zonas tensionadas (2 resoluciones) | estatal | 11 | 11 |

**Un fragmento por artículo**, porque el artículo es lo que una cita señala. Frente al troceo por tamaño fijo, medido sobre este mismo corpus: 1.000 caracteres con solapamiento produce 768 fragmentos de los cuales **el 47% abarca más de un artículo** y por tanto no se puede citar; por artículo produce 369 fragmentos y ninguno. Solo 13 artículos (3,7%) superan el presupuesto de 6.000 caracteres y se parten, siempre por párrafo. Números y alternativas en [ADR 0009](docs/decisions/0009-chunking-strategy.md).

La reingesta es idempotente en dos niveles: los metadatos del BOE (1,3 KB) deciden si hace falta descargar el texto, y el `content_hash` de cada fragmento decide si hace falta reescribir la fila.

**Embeddings y recuperación (implementado)**

Los 380 fragmentos tienen vector en pgvector y se buscan por similitud coseno con índice HNSW.

| | Medido sobre el corpus real |
|---|---|
| Indexación completa | 154.287 tokens · **0,0031 $** · 7,2 s |
| Reindexación rutinaria | 0 $ (solo se embebe lo que cambió) |
| Una búsqueda | ~250 ms, dominados por la llamada al proveedor |

`POST /api/v1/regulations/search` devuelve los fragmentos **con su puntuación**, antes de que ningún modelo los convierta en prosa: la calidad de la recuperación se ve, no se intuye.

**El umbral está medido, no elegido a ojo.** Con 16 preguntas, las de dominio puntúan entre 0,598 y 0,782 y las ajenas entre 0,148 y 0,403, así que `RETRIEVAL_MIN_SCORE=0.5` cae en mitad del hueco. Por debajo de ese umbral no se devuelve nada, aunque eso deje la lista vacía: entregar tres artículos irrelevantes a un modelo es pedirle que invente. Detalles en [ADR 0010](docs/decisions/0010-embedding-model-and-index.md).

**Cada vector sabe qué modelo lo hizo.** `EMBEDDING_MODEL` es configuración, y la búsqueda solo compara fragmentos embebidos con el modelo configurado: mezclar dos espacios vectoriales en un índice no falla, simplemente devuelve ruido. Cambiar de modelo es una variable más `make embed`.

**Generación fundamentada (implementado)**

```
POST /api/v1/regulations/ask
  └→ app/api/regulations.py                       (transporte)
       └→ app/domain/regulation_qa_service.py     (conductor)
            1. guardrails de entrada              (límites de pregunta, inyección, PII, moderación)
            2. app/generation/rag/retriever.py    (top-k con umbral; si no hay nada, termina aquí)
            3. app/generation/rag/context.py      (deduplica, ordena, numera, etiqueta el ámbito)
            4. prompts regulations_qa/v1          (responde solo con el contexto numerado)
            5. verificación de citas              (un número no recuperado se descarta)
```

**El modelo nunca escribe una cita.** Se le muestran fragmentos numerados y devuelve los **números** que ha usado; el servicio construye la cita a partir del fragmento recuperado. Un modelo al que le pides una URL te da una URL verosímil, y un enlace verosímil al artículo equivocado es peor que no tener enlace: quien lo sigue aterriza en el BOE y se fía de todo lo demás.

Si una respuesta se queda sin ninguna cita válida, se convierte en un "no lo sé". Una respuesta que nadie puede comprobar vale menos que admitir que no se sabe, porque desde fuera no se distinguen.

Medido de punta a punta contra el corpus y el modelo reales:

| Pregunta | Resultado | Latencia | Coste |
|---|---|---|---|
| "¿Cuál es la fianza legal en un alquiler de vivienda?" | responde citando **LAU art. 36** | 1,7 s | 0,0054 $ |
| "¿Qué información hay que dar en una oferta de alquiler?" (Cataluña) | responde citando **Ley 18/2007 art. 61** | 2,9 s | 0,0065 $ |
| "¿Qué tiempo hará mañana en Bilbao?" | rechaza **sin llamar al modelo** | 0,9 s | 0 $ |

Detalles y límites en [ADR 0011](docs/decisions/0011-grounded-answers-and-citations.md).

**Control de alucinación y securización (pendiente)**: la verificación actual es estructural (el artículo citado **se recuperó**), no semántica (el artículo **sostiene** la frase). Esa diferencia la cierra la fase de grounding.

**Agentes (pendiente)**: un agente con function calling que decide qué consultar (normativa, Catastro, precio de mercado) y un paso crítico que descarta las incidencias sin cita.

### **2.8. 🆕 Gestión de latencia, coste, calidad y seguridad**

**Latencia.** Una revisión completa tarda unos 6 segundos con Claude Haiku 4.5 y unos 3 con GPT-5.4 mini. Un rechazo por guardrail local es inmediato (unos 4 ms), porque la única capa que sale a la red se ejecuta la última. La caché (#12) eliminará la llamada al modelo en las revisiones repetidas.

**Coste.** La revisión más barata es la que no se pide: un acierto de caché cuesta 0 $ y 1 ms. Para el resto, cada revisión informa de lo que ha costado, calculado con una tabla de precios propia a partir del modelo que respondió de verdad. Medido sobre el mismo anuncio: **0,0057 $ con Claude Haiku 4.5** (2.340 + 678 tokens) y **0,0030 $ con GPT-5.4 mini** (1.176 + 464 tokens). Las capas que no necesitan el modelo (tamaño, inyección, datos personales) ahorran la llamada entera, y el límite de gasto está configurado en la consola del proveedor.

La búsqueda en la tabla usa el prefijo más largo, porque el proveedor responde con la versión fechada del modelo (`claude-haiku-4-5-20251001`) y una búsqueda exacta fallaría y cobraría cero. Un modelo desconocido devuelve coste vacío y deja un aviso en el log: un hueco es honesto, un cero es mentira.

**Disponibilidad.** El código pide al Router un modelo lógico (`listing-reviewer`) y nunca nombra un proveedor. Si Anthropic falla, responde OpenAI sin que el cliente se entere; el proveedor real aparece en `usage`. Probado con una clave primaria inválida: la revisión se completó igual.

**Coste de una consulta de normativa.** Tres tramos, medidos:

| | Latencia | Coste |
|---|---|---|
| Recuperación (embedding de la pregunta) | ~220 ms (p95: 380 ms) | 0,0000003 $ |
| Respuesta completa con citas | 1,7–2,9 s | ~0,005 $ |
| Rechazo sin llamar al modelo | 0,9 s | **0 $** |

Lo que cuesta no es buscar, es el contexto que la búsqueda produce: unos 4.600 tokens de entrada por respuesta. Bajar `MAX_CONTEXT_CHARS` es la palanca si el gasto importa.

**Calidad.** La salida se valida contra el esquema y, si no encaja, se le vuelve a pedir al modelo. El guardrail de salida descarta las incidencias que citan una norma fuera del checklist y recalcula el veredicto.

La recuperación **está medida**, no supuesta ([ADR 0012](docs/decisions/0012-retrieval-baseline-and-tuning.md)). Con un set dorado de 29 preguntas:

| | recall@1 | recall@3 | MRR | sin respuesta (fuera de dominio) |
|---|---:|---:|---:|---:|
| `dense-k5-t0.5` (configuración actual) | 82% | 95% | 0,871 | 86% |

Y el desglose que importa:

| Familia de preguntas | Artículo correcto en primera posición |
|---|---|
| Lenguaje legal | **10 / 10** |
| Paráfrasis (como pregunta un propietario) | **8 / 12** |
| Fuera de dominio | **6 / 7** |

**Los cuatro fallos son paráfrasis.** Ninguna pregunta con lenguaje legal falla. El problema de este sistema no es la calidad de la recuperación en general: es que las palabras del usuario no son las de la ley. Eso es lo que la reformulación de consulta y la búsqueda híbrida tienen que arreglar, y ahora hay con qué comprobarlo:

```bash
make benchmark-retrieval
```

La medición sistemática de las **respuestas** (fidelidad, exactitud de las citas, casos de regresión) llega en #4; este banco mide lo que llega al modelo, no lo que el modelo hace con ello.

**Seguridad.** Detallada en la sección 2.5: cuatro capas de entrada, el anuncio tratado como dato en el prompt, y los secretos solo por variables de entorno.

### **2.9. 🆕 Trazabilidad y observabilidad**

Cada revisión deja un evento JSON (`structlog`), pensado para contarse y no solo para leerse:

```json
{"event": "listing_review.completed", "prompt_version": "v2", "provider": "anthropic",
 "model": "claude-haiku-4-5-20251001", "input_tokens": 2340, "output_tokens": 678,
 "latency_ms": 6308, "estimated_cost_usd": 0.00573, "attempts": 1,
 "is_rental_listing": true, "level": "info", "timestamp": "2026-09-20T07:59:40.699454Z"}
```

Con esos campos se responde a lo que importa cuando algo va mal: qué versión del prompt se usó, qué proveedor respondió (y por tanto si saltó el fallback), cuánto tardó y cuánto costó.

El coste suma **todos los intentos**, no solo el último. Cuando el modelo devuelve algo que no encaja en el esquema, se le vuelve a pedir, y ese viaje también se paga: contar solo el intento final haría que un modelo que se equivoca a menudo pareciera más barato de lo que es. El campo `attempts` separa las dos causas de una subida de coste: más tokens o más reintentos. El dashboard y las evals de #4 se construyen contando estos eventos, no leyéndolos.

Los guardrails registran también lo suyo: `guardrail.moderation_unavailable` cuando el clasificador falla y se sigue adelante, y `guardrail.dropped_finding` cuando se descarta una incidencia que citaba una norma fuera del checklist.

### **2.10. 🆕 Decisiones técnicas**

> Resume las decisiones clave y enlaza su justificación en [`docs/decisions/`](docs/decisions/) (contexto, alternativas, decisión y consecuencias).

---

## 3. Modelo de Datos

### **3.1. Diagrama del modelo de datos:**

El modelo de datos es el **corpus normativo**: los documentos oficiales que se ingestan y los
fragmentos sobre los que se busca. No hay entidades de usuario: el sistema no guarda anuncios ni
cuentas, solo normativa pública ([ADR 0008](docs/decisions/0008-vector-store-and-migrations.md)).

```mermaid
erDiagram
    documents ||--o{ chunks : "se trocea en"

    documents {
        integer id PK
        text source_id UK "Identificador BOE, p. ej. BOE-A-1994-26003"
        text title
        text jurisdiction "state | catalonia"
        text doc_type "consolidated_law | resolution"
        text url "Enlace al texto consolidado"
        text boe_updated_at "fecha_actualizacion: dispara la reingesta"
        text corpus_version
        timestamptz ingested_at
    }

    chunks {
        integer id PK
        integer document_id FK
        text block_id "Bloque del texto consolidado, p. ej. a36"
        text article_title
        integer ordinal "Pieza dentro del bloque: 0 salvo artículos partidos"
        text text
        integer char_count
        jsonb metadata "fecha_vigencia, id_norma, citation_url"
        text content_hash "SHA-256: hace idempotente la reingesta"
        vector embedding "1536 dimensiones, índice HNSW coseno"
        text embedding_model "Qué modelo generó el vector"
        timestamptz embedded_at
        timestamptz created_at
    }
```

Estado actual del corpus: **6 documentos y 380 fragmentos**, todos con vector, construidos con
`make ingest`. Las versiones del BOE de las que se construyó quedan registradas en
[`corpus.lock.json`](corpus.lock.json).

La columna `embedding` es `vector(1536)` con índice HNSW (`vector_cosine_ops`), y cada fila
guarda el `embedding_model` que la generó, de modo que un cambio de modelo es visible en los
datos en vez de ser una suposición.

### **3.2. Descripción de entidades principales:**

**`documents`**: una fuente oficial ingestada. `source_id` es único, de modo que una norma existe
una sola vez en el corpus; `boe_updated_at` guarda la `fecha_actualizacion` que publica el BOE y
es lo que permite decidir si hay que volver a ingestarla. `jurisdiction` y `doc_type` están
restringidos por `CHECK` (`state` | `catalonia` y `consolidated_law` | `resolution`): son los ejes
por los que la recuperación filtra, así que la base de datos los defiende en vez de confiar en
que la aplicación no se equivoque.

**`chunks`**: el fragmento que se recupera y se cita, normalmente un artículo completo. Relación
`1:N` con `documents`, con borrado en cascada: reingestar una norma sustituye sus fragmentos sin
dejar huérfanos. La restricción única `(document_id, block_id, ordinal)` es la que hace que
ejecutar la ingesta dos veces no duplique nada. `metadata` va en `jsonb` porque sus campos
(`fecha_vigencia`, `id_norma`, `citation_url`) viajan siempre juntos hacia la cita y ninguno se
filtra por separado. `content_hash` es el SHA-256 del texto del fragmento: si no cambia, no hay
nada que reescribir ni que volver a embeber.

---

## 4. Especificación de la API

La especificación completa se genera sola y está en `http://localhost:8000/docs` (Swagger) y `http://localhost:8000/openapi.json`.

| Endpoint | Qué hace |
|---|---|
| `POST /api/v1/listings/review` | Revisa un anuncio de alquiler y devuelve incidencias, veredicto y coste |
| `POST /api/v1/regulations/search` | Busca en la normativa y devuelve los fragmentos con su puntuación |
| `POST /api/v1/regulations/ask` | Responde una pregunta sobre normativa con citas verificables al BOE |
| `GET /health` | Estado del servicio y del almacén del corpus |

```yaml
paths:
  /api/v1/listings/review:
    post:
      summary: Revisa un anuncio de alquiler y devuelve las incidencias detectadas
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              required: [text]
              properties:
                text: { type: string, description: Texto del anuncio }
                price_eur_month: { type: number, nullable: true }
                usable_surface_m2: { type: number, nullable: true }
                rooms: { type: integer, nullable: true }
                municipality: { type: string, nullable: true }
                energy_rating: { type: string, nullable: true }
      responses:
        "200":
          description: Revisión estructurada
          content:
            application/json:
              schema:
                type: object
                required: [findings, verdict, summary]
                properties:
                  findings:
                    type: array
                    items:
                      type: object
                      required: [category, severity, message, suggestion]
                      properties:
                        category:
                          type: string
                          enum: [energy_label, price_and_expenses, deposit_and_guarantees,
                                 agency_fees, surface, property_details, description_quality, other]
                        severity: { type: string, enum: [high, medium, low] }
                        message: { type: string }
                        suggestion: { type: string }
                        legal_basis: { type: string, nullable: true }
                  verdict: { type: string, enum: [approve, request_changes] }
                  summary: { type: string }
        "422":
          description: La petición no cumple el esquema
  /health:
    get:
      summary: Sonda de salud del servicio
      responses:
        "200":
          description: Servicio operativo
          content:
            application/json:
              schema:
                type: object
                properties:
                  status: { type: string, example: ok }
```

Ejemplo de petición:

```bash
curl -X POST http://localhost:8000/api/v1/listings/review \
  -H "Content-Type: application/json" \
  -d '{"text": "Piso de 2 habitaciones en Chamberí. Fianza de dos meses y honorarios de agencia a cargo del inquilino.", "price_eur_month": 1400, "municipality": "Madrid"}'
```

---

## 5. Historias de Usuario

> Documenta 3 de las historias de usuario principales utilizadas durante el desarrollo, teniendo en cuenta las buenas prácticas de producto al respecto.

**Historia de Usuario 1**

**Historia de Usuario 2**

**Historia de Usuario 3**

---

## 6. Tickets de Trabajo

> Documenta 3 de los tickets de trabajo principales del desarrollo, uno de backend, uno de frontend, y uno de bases de datos. Da todo el detalle requerido para desarrollar la tarea de inicio a fin teniendo en cuenta las buenas prácticas al respecto. 

**Ticket 1**

**Ticket 2**

**Ticket 3**

---

## 7. Pull Requests

> Documenta 3 de las Pull Requests realizadas durante la ejecución del proyecto

**Pull Request 1**

**Pull Request 2**

**Pull Request 3**

---

## 8. 🆕 Evaluación (evals)

> Describe la suite de evaluación: test sets, métricas (retrieval, generación, detección de defectos, latencia y coste), rúbrica del LLM-as-judge, casos de regresión y resultados por iteración. Detalle en [`docs/evals.md`](docs/evals.md).

---

## 9. 🆕 Limitaciones conocidas y próximos pasos

> Enumera las limitaciones actuales del sistema y cómo se resolverían, incluyendo cómo se integraría en un marketplace inmobiliario real.

