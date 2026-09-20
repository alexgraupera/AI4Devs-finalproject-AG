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

> Enumera y describe las prácticas de seguridad principales que se han implementado en el proyecto, añadiendo ejemplos si procede

### **2.6. Tests**

> Describe brevemente algunos de los tests realizados

### **2.7. 🆕 Arquitectura de IA: CAG → RAG → agentes**

> Explica cómo evoluciona el sistema desde el prototipo CAG hasta RAG con agentes: qué conocimiento vive en el contexto (CAG), qué se recupera (RAG: fuentes, chunking, embeddings, retrieval) y qué orquestan los agentes (herramientas, function calling, human-in-the-loop).

### **2.8. 🆕 Gestión de latencia, coste, calidad y seguridad**

> Explica cómo se gestiona cada aspecto: latencia (modelos, streaming, caché), coste (elección de modelos, tokens, límites de gasto, coste estimado por petición), calidad (evaluación, ver sección 8) y seguridad (guardrails de entrada y salida, prompt injection, protección de credenciales).

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

> Si tu backend se comunica a través de API, describe los endpoints principales (máximo 3) en formato OpenAPI. Opcionalmente puedes añadir un ejemplo de petición y de respuesta para mayor claridad

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

