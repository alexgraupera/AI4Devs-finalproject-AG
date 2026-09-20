> Detalla en esta sección los prompts principales utilizados durante la creación del proyecto, que justifiquen el uso de asistentes de código en todas las fases del ciclo de vida del desarrollo. Esperamos un máximo de 3 por sección, principalmente los de creación inicial o  los de corrección o adición de funcionalidades que consideres más relevantes.
Puedes añadir adicionalmente la conversación completa como link o archivo adjunto si así lo consideras


## Índice

1. [Descripción general del producto](#1-descripción-general-del-producto)
2. [Arquitectura del sistema](#2-arquitectura-del-sistema)
3. [Modelo de datos](#3-modelo-de-datos)
4. [Especificación de la API](#4-especificación-de-la-api)
5. [Historias de usuario](#5-historias-de-usuario)
6. [Tickets de trabajo](#6-tickets-de-trabajo)
7. [Pull requests](#7-pull-requests)

---

## 1. Descripción general del producto

> Asistente usado durante todo el proyecto: Claude Code (Opus 5).

**Prompt 1:**

> Ayúdame a recopilar ideas para el proyecto final. Quiero hacerlo individual y con la ayuda de la IA. Estoy trabajando en un marketplace inmobiliario, pero puedo enfocarlo desde otro punto de vista. Aunque encontrar un proyecto de mi sector, incluso podría utilizarlo para propuesta en mi trabajo.

De las cinco ideas propuestas se eligió el copiloto de calidad y cumplimiento de anuncios de alquiler, por tener datos públicos reales disponibles y encajar con las capas del programa.

**Prompt 2:**

> Antes de continuar con todo, quiero que valides todas las fuentes de datos que queremos utilizar en el proyecto. No quiero empezar nada y luego quedarme sin poder continuar.

Se validaron el BOE, el Catastro y SERPAVI con peticiones reales antes de escribir código. Dos decisiones salieron de aquí: las zonas tensionadas no se exponen como herramienta (no hay lista consolidada) y el precio de SERPAVI es un rango de mercado, nunca un tope legal.

**Prompt 3:**

> Es EXTREMADAMENTE IMPORTANTE que el proyecto final se ajuste totalmente a lo impartido en el curso y a los requerimientos del proyecto final. Valida que lo cumplimos a rajatabla.

Resultado: el documento [`docs/scope.md`](docs/scope.md), con las capacidades cubiertas, las que quedan fuera y por qué.

---

## 2. Arquitectura del Sistema

### **2.1. Diagrama de arquitectura:**

**Prompt 1:**

**Prompt 2:**

**Prompt 3:**

### **2.2. Descripción de componentes principales:**

**Prompt 1:**

> Implementa la fase 2: contrato de dominio, prompts Jinja2 versionados, wrapper de LLM con LiteLLM e Instructor, servicio conductor y router fino, con tests que nunca llamen al modelo real.

**Prompt 2:**

> El paquete debe estar organizado en capas por responsabilidad, y las arquitecturas de IA no deben importarse entre sí: solo componen en el conductor.

### **2.3. Descripción de alto nivel del proyecto y estructura de ficheros**

**Prompt 1:**

**Prompt 2:**

**Prompt 3:**

### **2.4. Infraestructura y despliegue**

**Prompt 1:**

**Prompt 2:**

**Prompt 3:**

### **2.5. Seguridad**

**Prompt 1:**

**Prompt 2:**

**Prompt 3:**

### **2.6. Tests**

**Prompt 1:**

**Prompt 2:**

**Prompt 3:**

---

### 3. Modelo de Datos

**Prompt 1:**

**Prompt 2:**

**Prompt 3:**

---

### 4. Especificación de la API

**Prompt 1:**

> Documenta en el README la especificación OpenAPI del endpoint de revisión, con un ejemplo de petición y de respuesta.

---

### 5. Historias de Usuario

**Prompt 1:**

**Prompt 2:**

**Prompt 3:**

---

### 6. Tickets de Trabajo

**Prompt 1:**

**Prompt 2:**

**Prompt 3:**

---

### 7. Pull Requests

**Prompt 1:**

**Prompt 2:**

**Prompt 3:**
