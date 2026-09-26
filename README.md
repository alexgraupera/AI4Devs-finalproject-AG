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

**https://ai4devs-rental-ui-ag.onrender.com**

Pública y sin credenciales. Está en el plan gratuito de Render: si nadie la ha usado en los últimos 15 minutos, la primera visita tarda hasta un minuto en despertar el servicio (la interfaz lo avisa mientras espera).

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
cuyo esquema corresponde al código que ejecuta. Puedes comprobarlo en `GET /ready`, que
informa del estado del almacén, de la caché y del presupuesto del día (`GET /health` solo dice si
el proceso está vivo, a propósito). Todos los puertos se publican solo en `127.0.0.1`.

Para probar la seguridad en local, define en `.env` `API_KEY` y `SERVICE_TOKEN`: la API los exige
y la interfaz los envía. Vacíos, la API queda abierta y avisa en cada petición.

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
`DATABASE_URL` el servicio arranca igual y `/ready` responde `"database": "disabled"`. Para
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

Render, en el plan gratuito, descrito como código en [`render.yaml`](render.yaml): coste de infraestructura cero y un despliegue por cada merge a `main` ([ADR 0021](docs/decisions/0021-hosting-on-render.md), guía completa en [`docs/deployment.md`](docs/deployment.md)).

```mermaid
flowchart LR
    user([Navegador]) -->|HTTPS| ui

    subgraph render[Render, Frankfurt]
        ui[Interfaz<br/>Streamlit]
        api[Servicio de IA<br/>FastAPI]
        db[(Postgres + pgvector)]
        cache[(Key Value · Redis)]
    end

    ui -->|HTTPS · token de servicio + clave| api
    api -->|red privada| db
    api -->|red privada| cache
    api -->|HTTPS| providers[Anthropic · OpenAI]
    api -->|HTTPS, al arrancar| boe[API de datos abiertos del BOE]
```

**Una imagen, dos servicios.** La API y la interfaz se construyen desde el mismo `Dockerfile`; solo cambia el comando. Postgres y Redis solo son accesibles desde la red privada.

**El despliegue es hacer merge a `main`.** El CI pasa lint, tipos, tests contra Postgres real y un escaneo de secretos (gitleaks) en cada pull request; Render construye y despliega tras el merge. Ningún secreto vive en el repositorio, en la imagen ni en el CI: las claves de los proveedores se escriben una vez en Render, y la clave y el token los genera la propia plataforma.

**Al arrancar, la API se prepara sola.** Aplica las migraciones y reconstruye el corpus desde el BOE si hace falta: la primera vez descarga las seis fuentes y las embebe (~10 s, 0,02 $); las siguientes ve que nada ha cambiado y no hace nada. Si el BOE no responde, arranca igual con lo que tiene.

**Rollback en un minuto.** Render guarda cada despliegue y vuelve a uno anterior sin reconstruir. Al apagar un contenedor en un despliegue, las revisiones en curso tienen hasta 120 s para terminar en vez de cortarse y pagarse dos veces.

Lo que cuesta el plan gratuito, dicho y no escondido: la API es pública (los servicios gratuitos no reciben tráfico privado), protegida por el token, la clave, el límite de peticiones y el tope de gasto; los servicios se duermen tras 15 minutos; y la base de datos gratuita caduca a los 30 días, lo que aquí se acepta porque el corpus se reconstruye solo.

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

**Dos capas de acceso, para que exponer el servicio requiera dos errores y no uno** ([ADR 0014](docs/decisions/0014-grounding-and-retrieval-security.md), [ADR 0020](docs/decisions/0020-access-spend-and-probes.md)):

| Guarda | Dónde | Qué hace |
|---|---|---|
| `X-Service-Token` | Middleware sobre toda la API | ¿Puedes hablar con este servicio? Solo lo tiene la interfaz, como lo tendría el backend de un marketplace |
| `X-API-Key` | Cada router de negocio, revisión incluida | ¿Qué endpoints puedes usar? Un endpoint nuevo bajo un router protegido queda protegido por estar ahí |
| Límite de peticiones | Los mismos routers | Ventana fija sobre Redis, 30/minuto por clave, con `Retry-After` en el 429 |
| Tope de gasto diario | Antes de cada llamada a un modelo | Al llegar a `DAILY_SPEND_CAP_USD` (2 $ por defecto) deja de llamar a modelos hasta medianoche UTC y responde 503 |

Las comparaciones son de tiempo constante, y un secreto ausente y uno erróneo reciben el **mismo** 401: decirle a un atacante cuál de las dos era es información gratis. Las sondas y la documentación OpenAPI quedan fuera a propósito: una sonda que necesita un secreto deja de funcionar el día que el secreto rota.

**En producción no arranca sin secretos.** Con `ENVIRONMENT=production`, una clave, el token, un proveedor, la base de datos o Redis vacíos impiden arrancar, nombrando lo que falta y nunca un valor. Un token vacío no falla más tarde: compara igual que la cabecera vacía de cualquiera y abre la puerta sin avisar. En desarrollo arranca igual y avisa en cada petición.

**El tope de gasto para, no avisa**, porque puede que nadie esté mirando cuando un bucle o el script de otro empieza a gastar. Una revisión cacheada se sirve aunque el presupuesto esté agotado, porque no cuesta nada.

El limitador y el tope **nunca tumban el servicio**: si Redis no responde, la petición pasa y se registra el fallo. Convertir la caída de una dependencia opcional en la caída del producto tiene las prioridades al revés.

**Sondas.** `/health` dice si el proceso está vivo y no toca nada: una sonda de vida que consulta la base de datos reinicia un servicio sano cada vez que la base tose. `/ready` dice si puede atender ahora (base de datos, caché y presupuesto) y responde 503 con `Retry-After` cuando no: es motivo para esperar, no para reiniciar.

### **2.6. Tests**

> Describe brevemente algunos de los tests realizados

### **2.7. 🆕 Arquitectura de IA: CAG → RAG → agentes**

El sistema apila tres arquitecturas que **no se conocen entre sí**: solo componen en los servicios conductores de `app/domain/`. CAG y RAG están construidos; los agentes, que usan ambos a la vez, son la capa siguiente (#3).

**CAG: conocimiento en el prompt (implementado)**

En el sentido del curso, CAG es el prompt ensamblado con conocimiento estable más la caché que evita preguntar dos veces. El conocimiento de la revisión es un checklist corto y estable: cinco puntos normativos, cada uno con el artículo que lo respalda, más criterios de calidad del anuncio. Vive en el prompt de sistema, versionado en `app/foundation/prompts/listing_review/v1/`, y no en el código ni en una base de datos. El flujo de una revisión es:

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

**Caché semántica: medida y descartada.** Serviría la revisión de un anuncio a otro «parecido», y en este dominio lo parecido es justo lo peligroso. Medido con pares de anuncios: el mismo piso con **una fianza de dos meses en lugar de una** se parece más al original (0,996) que el mismo piso con las frases reordenadas (0,912). Cualquier umbral que ahorre llamadas le daría una revisión limpia a un anuncio ilegal, porque los cambios que alteran el veredicto son los más pequeños que existen: una palabra o un número ([ADR 0019](docs/decisions/0019-no-semantic-cache.md), `make benchmark-semantic-cache`).

**RAG: corpus ingestado (implementado)**

El checklist del prompt cubre lo que siempre hay que comprobar; el RAG cubre lo que hay que consultar. El corpus del BOE vive en la base de datos, troceado por artículo y embebido.

**Por qué recuperar y no meter toda la normativa en el prompt.** El corpus completo son **187.883 tokens** de Claude: el 94% de la ventana de Haiku 4.5 antes de añadir la pregunta, cuando la regla práctica es no pasar del 50-70%. Costaría ~0,19 $ por pregunta frente a los 0,016 $ medidos con RAG, y una pregunta fuera de dominio, que hoy se rechaza sin llamar al modelo (0 $), costaría lo mismo que una buena. El fine-tuning tampoco encaja: no hay datos con los que entrenar, la ley cambia varias veces al año y un modelo entrenado no puede citar de dónde saca nada ([ADR 0016](docs/decisions/0016-rag-not-cag-or-fine-tuning.md)).

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
| Indexación completa | 154.287 tokens · **0,0201 $** · 9,5 s |
| Reindexación rutinaria | 0 $ (solo se embebe lo que cambió) |
| Una búsqueda | ~250 ms, dominados por la llamada al proveedor |

`POST /api/v1/regulations/search` devuelve los fragmentos **con su puntuación**, antes de que ningún modelo los convierta en prosa: la calidad de la recuperación se ve, no se intuye.

**El modelo de embeddings está medido, no heredado.** `text-embedding-3-large` recortado a 1.536 dimensiones (cabe en la misma columna, sin migración) frente a `text-embedding-3-small`, cada uno con su umbral: de punta a punta, las preguntas respondidas pasan del 82% al **91%** y las que citan el artículo esperado del 77% al **86%**, con los rechazos fuera de dominio intactos (100%) y un 8% más de coste por pregunta ([ADR 0015](docs/decisions/0015-embedding-model-measured.md)).

**El umbral es de cada modelo.** El modelo grande puntúa todo más bajo: con el 0,5 del pequeño, dos paráfrasis se quedaban sin ningún artículo. Barrido sobre el set dorado, `RETRIEVAL_MIN_SCORE=0.40` conserva todas las preguntas respondibles y deja pasar la misma pregunta fuera de dominio que ya dejaba el pequeño, que la generación y la verificación rechazan después. Por debajo del umbral no se devuelve nada, aunque eso deje la lista vacía: entregar tres artículos irrelevantes a un modelo es pedirle que invente.

**El índice no se ajusta, y está medido por qué.** Con 380 fragmentos el planificador de PostgreSQL ni usa el índice HNSW: hace una búsqueda exacta (recall del 100% por definición) en 4,4 ms. Ajustar `ef_search` sería afinar algo que no se lee; el ADR 0015 dice a partir de qué tamaño y cómo.

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

**La primera frase tiene que seguir siendo cierta al final.** El prompt `v2` prohíbe abrir con un veredicto que la respuesta vaya a desdecir después: probando a mano apareció un "No, el casero no puede pedir 3 meses de fianza" que terminaba en "el máximo total sería tres meses". Todo era verdad por separado, y quien leyera solo la primera frase se llevaba lo contrario de la conclusión.

**Y el rechazo dice dónde está el borde**: nombra las cuatro normas indexadas y los temas que quedan fuera (fiscalidad, comunidades de propietarios, procedimientos judiciales), para que quien pregunte distinga "lo has preguntado mal" de "eso no lo leo".

Medido de punta a punta contra el corpus y el modelo reales:

| Pregunta | Resultado | Latencia | Coste |
|---|---|---|---|
| "¿Cuál es la fianza legal en un alquiler de vivienda?" | responde citando **LAU art. 36** | 1,7 s | 0,0054 $ |
| "¿Qué información hay que dar en una oferta de alquiler?" (Cataluña) | responde citando **Ley 18/2007 art. 61** | 2,9 s | 0,0065 $ |
| "¿Qué tiempo hará mañana en Bilbao?" | rechaza **sin llamar al modelo** | 0,9 s | 0 $ |

Detalles y límites en [ADR 0011](docs/decisions/0011-grounded-answers-and-citations.md).

**Verificación de que el artículo sostiene la frase (implementado)**

La comprobación de citas es *estructural*: demuestra que el artículo citado se recuperó. Un modelo todavía puede citar un artículo real, con enlace que funciona, para una regla que ese artículo no contiene, y ese fallo es invisible para todo lo anterior. Solo leyendo ambos se detecta.

Un juez lee los artículos citados y la respuesta, extrae las afirmaciones jurídicas y marca cuáles están sostenidas. Dos comprobaciones deterministas van antes y no cuestan nada: sin citas, o citando un fragmento que no está en el contexto, se rechaza sin preguntar a nadie.

**La política que puse primero era incorrecta, y la medición lo dijo.** Rechazar por *cualquier* afirmación no sostenida tiraba el **23% de las respuestas correctas**, casi siempre por frases de encuadre o por afirmaciones negativas que ningún fragmento puede sostener. Ahora es un umbral de confianza del 0,7 y el prompt excluye esos casos:

| | Antes | Después |
|---|---|---|
| Preguntas respondibles contestadas | 100% | **91%** |
| Preguntas fuera de dominio rechazadas | 86% | **100%** |

Ese 100% es lo importante: la fuga que el [ADR 0012](docs/decisions/0012-retrieval-baseline-and-tuning.md) aceptó a sabiendas queda cerrada por el otro lado. Una respuesta que el artículo citado no sostiene no se publica, diga lo que diga la puntuación de similitud.

**Agente: donde CAG y RAG se juntan (implementado)**

La revisión de siempre solo puede citar los cinco artículos que lleva el prompt: no puede consultar nada. El agente sí. Lee el checklist en su prompt (CAG), busca en el corpus del BOE con una herramienta (RAG) y decide qué comprobar y en qué orden ([ADR 0024](docs/decisions/0024-agent-loop-and-tools.md)).

```
POST /api/v1/listings/agent-review
  └→ app/domain/agent_review_service.py        (conductor: guardrails, tope de gasto, citas, guardrail de salida)
       └→ app/generation/agentic/loop.py        (razona → actúa → observa, escrito a mano)
            ├→ check_listing_fields              (código, nunca el modelo: datos que faltan y contradicciones)
            ├→ search_regulations                (el retriever, a través de un puerto)
            └→ submit_review                     (la revisión, validada contra el esquema)
```

| Lo que no se deja al modelo | Cómo |
|---|---|
| Parar | 6 iteraciones, 90 s o la misma llamada fallando dos veces; entonces entrega lo que tiene y la respuesta avisa de que puede estar incompleta |
| Citar | El modelo da números de fragmento; la cita se construye con lo que devolvió la búsqueda y un número inventado se descarta |
| Afirmar algo legal | Una incidencia legal sin un fragmento leído detrás (y fuera del checklist) no llega al usuario |
| Comprobar los datos | Una herramienta en código que lee el anuncio en revisión: no acepta argumentos, así que el modelo no puede comprobar otro |

Cada paso, con lo que el modelo escribió al decidirlo, vuelve en la respuesta y se ve en la página «Revisión con agente». Las dos revisiones siguen vivas una junto a otra para poder compararlas con números (#52).

**Actor, crítico y jefe** ([ADR 0025](docs/decisions/0025-actor-critic-boss.md)). Tras el agente, un **crítico en el otro proveedor** lee cada incidencia contra el anuncio y contra los artículos que cita, enteros, y dice por qué no se sostiene (contradice el anuncio, la regla no está en la fuente, artículo equivocado). El **jefe** es una función, no un modelo: acepta si se sostiene el 70%, devuelve la revisión al agente una vez con los rechazos citados, o la **escala a una persona**. Una incidencia rechazada no llega al usuario.

Y en los dos lados **el modelo cita y el código comprueba**: una incidencia sobre lo que dice el anuncio lleva la frase del anuncio, y el crítico solo puede decir que el anuncio la contradice citando dónde. Una cita que no está en el anuncio no cuenta. Se llegó ahí probando a mano: la primera versión del crítico tiró la incidencia correcta de la fianza y dejó pasar una infracción inventada.

**Siguen** el grafo con estado persistente (#41) y la pausa para una persona (#42).

### **2.8. 🆕 Gestión de latencia, coste, calidad y seguridad**

**Latencia.** Una revisión completa tarda unos 6 segundos con Claude Haiku 4.5 y unos 3 con GPT-5.4 mini. Un rechazo por guardrail local es inmediato (unos 4 ms), porque la única capa que sale a la red se ejecuta la última. Una revisión repetida la sirve la caché exacta en ~1 ms, sin llamar al modelo.

**Coste.** La revisión más barata es la que no se pide: un acierto de caché cuesta 0 $ y 1 ms. Para el resto, cada revisión informa de lo que ha costado, calculado con una tabla de precios propia a partir del modelo que respondió de verdad. Medido sobre el mismo anuncio: **0,0057 $ con Claude Haiku 4.5** (2.340 + 678 tokens) y **0,0030 $ con GPT-5.4 mini** (1.176 + 464 tokens). Las capas que no necesitan el modelo (tamaño, inyección, datos personales) ahorran la llamada entera. El gasto del día tiene un tope propio que corta las llamadas al llegar a él (2 $ por defecto, unas 350 revisiones), y el límite de la consola del proveedor queda como última línea.

La búsqueda en la tabla usa el prefijo más largo, porque el proveedor responde con la versión fechada del modelo (`claude-haiku-4-5-20251001`) y una búsqueda exacta fallaría y cobraría cero. Un modelo desconocido devuelve coste vacío y deja un aviso en el log: un hueco es honesto, un cero es mentira.

**Disponibilidad.** El código pide al Router un modelo lógico (`listing-reviewer`) y nunca nombra un proveedor. Si Anthropic falla, responde OpenAI sin que el cliente se entere; el proveedor real aparece en `usage`. Probado con una clave primaria inválida: la revisión se completó igual. Y probado de verdad sin querer: el 25 de septiembre la cuenta de Anthropic alcanzó su límite mensual y rechazó todas las llamadas hasta el 1 de octubre; el servicio siguió respondiendo con OpenAI sin cambiar una línea ([ADR 0023](docs/decisions/0023-a-model-per-role.md)).

**Un modelo por papel.** Quien escribe (Claude Haiku 4.5) no es quien verifica: el juez de la verificación de citas y el crítico del agente van en el otro proveedor (GPT-5.4 mini), para no compartir los puntos ciegos de quien escribió. Cada llamada tiene un tiempo máximo (45 s), un presupuesto de tokens (4.000) y temperatura 0, y una respuesta cortada por el presupuesto falla con su nombre en vez de por accidente. Se probó un reranker más barato (GPT-5.4 nano) y se descartó: pierde 8 puntos de recall@1.

**Coste de una consulta de normativa.** Tres tramos, medidos:

| | Latencia | Coste |
|---|---|---|
| Recuperación (embedding de la pregunta) | ~220 ms (p95: 380 ms) | 0,0000003 $ |
| Reranking de 20 candidatos a 5 | ~2,4 s | ~0,009 $ |
| Verificación de que los artículos sostienen la respuesta | ~0,8 s | ~0,001 $ |
| Respuesta completa con citas (todo incluido) | **~6-9 s** (p50, según la carga del proveedor) | **~0,016 $** |
| Rechazo sin llamar al modelo | 0,9 s | **0 $** |

Lo que cuesta no es buscar, es lo que un modelo tiene que leer: unos 7.000 tokens el reranking y 4.600 la generación. `RERANK_ENABLED=false` devuelve la respuesta a ~2 s y ~0,005 $, a cambio de 9 puntos de recall@1.

**Calidad.** La salida se valida contra el esquema y, si no encaja, se le vuelve a pedir al modelo. El guardrail de salida descarta las incidencias que citan una norma fuera del checklist y recalcula el veredicto.

La recuperación **está medida**, no supuesta ([ADR 0012](docs/decisions/0012-retrieval-baseline-and-tuning.md)). Con un set dorado de 29 preguntas:

| | recall@1 | recall@3 | MRR | sin respuesta (fuera de dominio) |
|---|---:|---:|---:|---:|
| `dense`, `text-embedding-3-small` (línea base) | 82% | 95% | 0,871 | 86% |
| `dense+rerank`, `text-embedding-3-small` | 86-91% | 100% | 0,924-0,955 | 86% |
| `dense`, `text-embedding-3-large` | 86% | 100% | 0,932 | 86% |
| **`dense+rerank`, `text-embedding-3-large` (configuración actual)** | **95%** | **100%** | **0,977** | **86%** |

El reranking es un modelo y varía entre ejecuciones: por eso su fila del modelo pequeño es un rango (ADR 0013 y ADR 0015).

Y el desglose que importa:

| Familia de preguntas | Artículo correcto en primera posición |
|---|---|
| Lenguaje legal | **10 / 10** |
| Paráfrasis (como pregunta un propietario) | **8 / 12** |
| Fuera de dominio | **6 / 7** |

**Los cuatro fallos de la línea base eran paráfrasis.** Ninguna pregunta con lenguaje legal fallaba: el problema no era la recuperación en general, sino que las palabras del usuario no son las de la ley.

Se atacó con tres técnicas y **dos de las tres hipótesis resultaron falsas** ([ADR 0013](docs/decisions/0013-advanced-retrieval-measured.md)):

| Técnica | Resultado | Decisión |
|---|---|---|
| Búsqueda híbrida (full-text + vectorial) | recall@1 **baja** de 82% a 77% | **eliminada** |
| Reformulación de consulta | recall sube, pero los rechazos **caen del 86% al 57%** | **eliminada** |
| **Reranking con modelo** | recall@1 **82% → 91%**, rechazos intactos | **conservada** |

El reranking funciona porque la recuperación va ancha (20 candidatos) y un modelo que **lee** los artículos elige los 5 mejores. Con 10 candidatos la mejora desaparece entera: el artículo que faltaba no está en el grupo, y no hay nada que rescatar. Cuesta ~2,4 s y ~0,009 $ por pregunta.

Lo eliminado se ha borrado del código, no desactivado con un flag: una opción que nadie activa es coste de mantenimiento más una mentira en la configuración. Los números que lo justifican están en el ADR.

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

La capa RAG registra lo suyo con la misma intención de que se pueda **contar**: `regulations_qa.invented_citation` cuando el modelo cita un fragmento que no se recuperó, `regulations_qa.grounding_failed` con las afirmaciones concretas que el artículo no sostenía, `regulations_qa.no_context` cuando no se llama al modelo porque no había nada que leer, y `rate_limit.exceeded` / `security.rejected` en la capa de acceso. El coste de una respuesta suma **las tres llamadas** (reranking, generación y verificación): informar solo de la generación dejaría el panel de costes callada pero sistemáticamente equivocado.

### **2.10. 🆕 Decisiones técnicas**

> Resume las decisiones clave y enlaza su justificación en [`docs/decisions/`](docs/decisions/) (contexto, alternativas, decisión y consecuencias).

Cada decisión tiene su registro con el contexto, las alternativas, lo que se midió y las consecuencias. Varias se tomaron **al revés de lo que se esperaba**, porque la medición lo dijo: están marcadas con ⚠️.

| ADR | Decisión |
|---|---|
| [0001](docs/decisions/0001-stack-and-project-structure.md) | Python + FastAPI + Streamlit, capas por responsabilidad y arquitecturas de IA que solo se componen en el conductor |
| [0002](docs/decisions/0002-prompt-strategy-and-checklist.md) | El checklist normativo va en el prompt (CAG); la pregunta abierta, a recuperación |
| [0003](docs/decisions/0003-review-output-schema.md) | Esquema de la revisión: hallazgos antes que veredicto, severidad como enum |
| [0004](docs/decisions/0004-guardrails.md) | Cuatro capas de entrada, de la más barata a la más cara, que rechazan y nunca corrigen |
| [0005](docs/decisions/0005-provider-fallback-cost-and-observability.md) | Anthropic con fallback a OpenAI, coste por llamada con tabla propia y logs estructurados |
| [0006](docs/decisions/0006-llm-wrapper-litellm-instructor.md) | Una sola puerta al LLM: LiteLLM + Instructor |
| [0007](docs/decisions/0007-exact-match-cache.md) | Caché exacta con la clave sobre los prompts completos, no sobre el anuncio |
| [0008](docs/decisions/0008-vector-store-and-migrations.md) | PostgreSQL + pgvector y esquema en migraciones escritas a mano |
| [0009](docs/decisions/0009-chunking-strategy.md) | Un fragmento por artículo, medido contra el troceo por tamaño fijo |
| [0010](docs/decisions/0010-embedding-model-and-index.md) | HNSW coseno y el modelo de embeddings por fila (modelo y umbral sustituidos por 0015) |
| [0011](docs/decisions/0011-grounded-answers-and-citations.md) | El modelo nunca escribe una cita: devuelve números que el servicio resuelve |
| [0012](docs/decisions/0012-retrieval-baseline-and-tuning.md) | Set dorado de 29 preguntas en tres familias, y top-k y umbral ajustados con él |
| [0013](docs/decisions/0013-advanced-retrieval-measured.md) | ⚠️ Búsqueda híbrida y reformulación medidas y **eliminadas**; reranking conservado |
| [0014](docs/decisions/0014-grounding-and-retrieval-security.md) | ⚠️ Verificación de que el artículo sostiene la respuesta, con umbral y no todo-o-nada |
| [0015](docs/decisions/0015-embedding-model-measured.md) | `text-embedding-3-large` a 1.536 dimensiones con su umbral; por qué no se ajusta el índice |
| [0016](docs/decisions/0016-rag-not-cag-or-fine-tuning.md) | Por qué RAG y no toda la normativa en el prompt ni fine-tuning |
| [0017](docs/decisions/0017-api-not-mcp.md) | Una API HTTP y no un servidor MCP; dónde entrarían MCP y A2A |
| [0018](docs/decisions/0018-data-privacy-and-providers.md) | Qué datos llegan a qué proveedor, y por qué los personales se rechazan en la puerta |
| [0019](docs/decisions/0019-no-semantic-cache.md) | ⚠️ Caché semántica medida y **descartada**: serviría la revisión equivocada |
| [0020](docs/decisions/0020-access-spend-and-probes.md) | Token de servicio y claves por router, tope de gasto diario que corta, arranque que falla sin secretos, vida ≠ disponibilidad |
| [0021](docs/decisions/0021-hosting-on-render.md) | Render gratuito descrito como Blueprint; lo que cuesta el plan gratuito y por qué Hugging Face no servía |
| [0022](docs/decisions/0022-answer-evaluation.md) | Evaluación de respuestas al estilo RAGAS con un juez de otro proveedor: el modelo lee, el código cuenta |
| [0023](docs/decisions/0023-a-model-per-role.md) | Un modelo por papel (el juez en el otro proveedor) y cada llamada acotada; el reranker barato, medido y descartado |
| [0024](docs/decisions/0024-agent-loop-and-tools.md) | El agente: bucle escrito a mano, herramientas, salidas forzadas y lo que no se le confía al modelo |
| [0025](docs/decisions/0025-actor-critic-boss.md) | ⚠️ Actor, crítico y jefe; el modelo cita y el código comprueba. Tres versiones, cada una por un fallo encontrado a mano |

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
| `POST /api/v1/listings/agent-review` | La misma revisión hecha por un agente que consulta la normativa: incidencias con sus citas al BOE, los pasos que dio y el coste |
| `POST /api/v1/regulations/search` | Busca en la normativa y devuelve los fragmentos con su puntuación |
| `POST /api/v1/regulations/ask` | Responde una pregunta sobre normativa con citas verificables al BOE |
| `GET /health` | Sonda de vida: el proceso responde (sin tocar nada) |
| `GET /ready` | Sonda de disponibilidad: base de datos, caché y presupuesto del día; 503 si no puede atender |

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
      summary: Sonda de vida del proceso
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

**Hoy está medida la recuperación.** Un set dorado de 29 preguntas en tres familias (lenguaje legal, paráfrasis y fuera de dominio) con recall@k, MRR y tasa de no-respuesta, ejecutable con `make benchmark-retrieval` ([`benchmarks/retrieval/`](benchmarks/retrieval/README.md)). Con él se ajustaron el umbral y el top-k ([ADR 0012](docs/decisions/0012-retrieval-baseline-and-tuning.md)), se eliminaron la búsqueda híbrida y la reformulación y se conservó el reranking ([ADR 0013](docs/decisions/0013-advanced-retrieval-measured.md)), y se calibró la verificación de citas ([ADR 0014](docs/decisions/0014-grounding-and-retrieval-security.md)). Los resultados están en la sección 2.8.

**Y están medidas las respuestas** (`make eval-answers`, [ADR 0022](docs/decisions/0022-answer-evaluation.md)): las 32 preguntas pasan por el servicio real y un juez de **otro proveedor** (GPT-5.4 mini) las califica con una rúbrica versionada. Métricas al estilo RAGAS: las de recuperación salen exactas de las etiquetas y las de generación del juez, que lista las afirmaciones mientras el código hace las cuentas.

| Prompt | Respondidas | Rechazos fuera de dominio | Citan el artículo esperado | Fidelidad | Corrección | Caso de regresión #34 |
|---|---:|---:|---:|---:|---:|---|
| v1 | 84% | 100% | 76% | 0,95 | 0,68 | ❌ se niega a responder |
| **v2 (actual)** | **92%** | **100%** | **88%** | 0,90 | **0,76** | ❌ la primera frase aún se contradice |

**La evaluación encontró lo que la prueba a mano no vio:** el arreglo del bug #34 está incompleto. Por eso existe un caso de regresión, y por eso se ha visto fallar antes de darlo por bueno. La mitad del coste de una respuesta es el reranking (0,0077 $ de 0,0164 $).

---

## 9. 🆕 Limitaciones conocidas y próximos pasos

> Enumera las limitaciones actuales del sistema y cómo se resolverían, incluyendo cómo se integraría en un marketplace inmobiliario real.

**El corpus son cuatro normas.** LAU, Ley 12/2023, RD 390/2021 y la ley catalana de vivienda. La fiscalidad del alquiler (IRPF), las comunidades de propietarios, los procedimientos judiciales y la normativa de las otras quince comunidades autónomas **no están**, y el asistente lo dice en vez de improvisar. Ampliarlo es añadir líneas a `app/ingestion/sources.py`; cada norma nueva cuesta unos milésimos de dólar en embeddings.

**Las resoluciones de zonas tensionadas se añaden a mano.** El BOE no publica una lista consolidada legible por máquina, así que cada trimestre alguien tiene que añadir el identificador nuevo. El detector de deriva semanal avisa de las leyes que cambian, no de las resoluciones que aparecen.

**El juez que verifica es el mismo modelo barato que escribe.** Se equivoca a veces en ambos sentidos: midiendo sobre 22 preguntas marcó como no sostenida una afirmación que sí estaba en el artículo. Un juez más capaz costaría más por pregunta; ese trade no está medido.

**El set dorado son 29 preguntas.** Suficiente para decidir entre técnicas cuyas diferencias son grandes, insuficiente para afinar. Una pregunta que se mueve cambia el recall tres puntos.

**Los datos personales se detectan a medias.** Emails, teléfonos e IBAN se rechazan antes de llamar a nadie; nombres, DNI/NIE y direcciones no se detectan. El siguiente paso es Presidio con reconocedores españoles, enmascarando lo que el anuncio no necesita ([ADR 0018](docs/decisions/0018-data-privacy-and-providers.md)).

**Una API, todavía no un agente para otros agentes.** El servicio se consume por HTTP. Ofrecerlo por MCP para uso interno o por A2A a los agentes de otros portales sería un adaptador sobre la misma API, con sus propias credenciales ([ADR 0017](docs/decisions/0017-api-not-mcp.md)).

**La clave de acceso es un secreto compartido.** Detrás de la interfaz, todos los visitantes comparten la clave de la interfaz, así que el límite de peticiones es global en la demo pública (el tope de gasto es el límite real). Límites por visitante exigirían que la interfaz reenviara una identidad del visitante en la que la API confiara porque el token avala a la interfaz; claves por llamante con rotación y cuotas son el siguiente paso con más de un cliente.

