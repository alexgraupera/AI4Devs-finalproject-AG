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

**Sin Docker (desarrollo):**

```bash
make install   # uv sync
make api       # API con recarga automática en :8000
make ui        # en otra terminal: interfaz en :8501
make verify    # lint, formato, tipos y tests
```

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
│   └── api/                  # Routers finos (transporte)
├── streamlit_app.py          # Cliente Streamlit (solo habla con la API por HTTP)
├── tests/                    # Tests, con la misma estructura que el paquete
├── docs/
│   ├── data-sources/         # Guías y ejemplos ejecutables de las fuentes de datos públicas
│   └── decisions/            # Registro de decisiones de arquitectura (ADR)
├── Dockerfile                # Imagen única para la API y la interfaz
├── docker-compose.yml        # Servicios api (:8000) y ui (:8501)
├── Makefile                  # Comandos de desarrollo y verificación
└── .github/workflows/ci.yml  # CI: make verify en cada pull request
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
            1. app/foundation/prompts/loader.py   (plantillas Jinja2 versionadas)
            2. app/foundation/llm/wrapper.py      (LiteLLM + Instructor, con reintentos)
            3. ListingReview                      (salida validada contra el esquema)
```

La salida es un objeto `ListingReview` validado: una lista de incidencias con categoría, gravedad, mensaje, sugerencia y base legal, más un veredicto y un resumen. Si el modelo no devuelve algo que encaje en el esquema, Instructor se lo vuelve a pedir; no llega texto libre a la interfaz.

El acceso al modelo pasa siempre por `LLMWrapper`, el único módulo que importa `litellm`. Por eso el modelo es configuración (`LLM_MODEL=anthropic/claude-haiku-4-5`) y los tests sustituyen el LLM sin tocar la red. Decisiones en [ADR 0002](docs/decisions/0002-prompt-strategy-and-checklist.md), [ADR 0003](docs/decisions/0003-review-output-schema.md) y [ADR 0006](docs/decisions/0006-llm-wrapper-litellm-instructor.md).

**Caché (pendiente)**: acierto exacto por SHA-256 del prompt completo y, después, acierto por similitud semántica, para no pagar dos veces la misma revisión.

**RAG (pendiente)**: la normativa completa del BOE indexada en pgvector, para responder preguntas abiertas sobre alquiler con citas verificables. El checklist del prompt cubre lo que siempre hay que comprobar; el RAG cubre lo que hay que consultar.

**Agentes (pendiente)**: un agente con function calling que decide qué consultar (normativa, Catastro, precio de mercado) y un paso crítico que descarta las incidencias sin cita.

### **2.8. 🆕 Gestión de latencia, coste, calidad y seguridad**

**Latencia.** Una revisión completa tarda unos 7 segundos con Claude Haiku 4.5. Un rechazo por guardrail local es inmediato (unos 4 ms), porque la única capa que sale a la red se ejecuta la última. La caché (#12) eliminará la llamada al modelo en las revisiones repetidas.

**Coste.** El modelo por defecto es el más barato de su familia, y la tarea (un texto corto, un esquema pequeño) no justifica otro más caro: media revisión cuesta del orden de medio céntimo. Las capas que no necesitan el modelo (tamaño, inyección, datos personales) ahorran la llamada entera. El límite de gasto está configurado en la consola del proveedor. El coste medido por petición llega en #10.

**Calidad.** La salida se valida contra el esquema y, si no encaja, se le vuelve a pedir al modelo. El guardrail de salida descarta las incidencias que citan una norma fuera del checklist y recalcula el veredicto. La medición sistemática con métricas y casos de regresión llega en #4.

**Seguridad.** Detallada en la sección 2.5: cuatro capas de entrada, el anuncio tratado como dato en el prompt, y los secretos solo por variables de entorno.

### **2.9. 🆕 Trazabilidad y observabilidad**

> Describe los logs, trazas de agentes y métricas registradas (modelo, tokens, latencia, coste) y cómo ayudan a depurar el sistema.

### **2.10. 🆕 Decisiones técnicas**

> Resume las decisiones clave y enlaza su justificación en [`docs/decisions/`](docs/decisions/) (contexto, alternativas, decisión y consecuencias).

---

## 3. Modelo de Datos

### **3.1. Diagrama del modelo de datos:**

> Recomendamos usar mermaid para el modelo de datos, y utilizar todos los parámetros que permite la sintaxis para dar el máximo detalle, por ejemplo las claves primarias y foráneas.


### **3.2. Descripción de entidades principales:**

> Recuerda incluir el máximo detalle de cada entidad, como el nombre y tipo de cada atributo, descripción breve si procede, claves primarias y foráneas, relaciones y tipo de relación, restricciones (unique, not null…), etc.

---

## 4. Especificación de la API

La especificación completa se genera sola y está en `http://localhost:8000/docs` (Swagger) y `http://localhost:8000/openapi.json`.

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

