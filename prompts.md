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

**Prompt 4:**

> El proyecto de final de master tiene actualmente una interfaz de streamlit, pero creo que las utilidades desarrolladas se verían mucho más consolidadas si se hiciera un frontend que simule un marketplace inmobiliario y que adapte estas herramientas a un flujo. El marketplace puede (de hecho debe) tener datos y diseño fake, pero las herramientas deben funcionar y tener un flujo y utilidad coherente. Me gusta mucho el diseño de esta web: https://novavoice.app/ y para mostrar anuncios (listings) de ejemplos este diseño también me gusta https://www.immobilienscout24.de/en/search/es/balearische-inseln/mallorca/apartments-for-sale?enteredFrom=one_step_search

Se planificó como seis fases ([#83](https://github.com/alexgraupera/AI4Devs-finalproject-AG/issues/83)) y el resultado es Umbral: cada herramienta donde la usaría un portal, con un servidor web propio que guarda las credenciales ([ADR 0036](docs/decisions/0036-marketplace-frontend.md)). Tras la segunda fase, un ajuste del mismo usuario convirtió el bloque de preguntas de la ficha en el asistente flotante:

> La verdad es que está muy bien, pero, en la ficha se podría hacer como el típico asistente que aparece siempre en la posición derecha final de la página y al hacer clic se abre una caja que puedas preguntarle?

---

## 2. Arquitectura del Sistema

> Casi todo el desarrollo se hizo con dos comandos de las skills de Codely sobre las issues del repositorio: `/codely-plan-create-github <issue>` convierte una issue padre en un plan de fases, cada una una issue con sus contratos públicos, sus tests y su lista de tareas; y `/codely-plan_phase-implement-github <issue>` implementa la siguiente fase pendiente, la verifica (`make verify`) y se detiene para revisión. Los prompts de esta página son los que tomaron las decisiones, copiados tal cual se escribieron (salvo erratas evidentes).

### **2.1. Diagrama de arquitectura:**

**Prompt 1:**

> Dos cosas:
> 1. Como puedo probarlo en local
> 2. En el curso se utilizan dos modelos, o al menos piden utilizar dos modelos en el proyecto de referencia, uno de Anthropic y otro de OpenAI

De aquí salió el Router de LiteLLM con un modelo lógico y fallback entre los dos proveedores ([ADR 0005](docs/decisions/0005-provider-fallback-cost-and-observability.md)), que más tarde se convirtió en un modelo por papel ([ADR 0023](docs/decisions/0023-a-model-per-role.md)).

**Prompt 2:**

> Ok. Para estar alineados. Es importante seguir las directrices y bases del master, es decir, basarse en lo que han enseñado. Eso es lo que debería cumplir el proyecto final. Podemos aportar algo de cosecha propia, por supuesto, pero siempre sobre la base impartida.
>
> Por otro lado, he añadido el repositorio que han utilizado para impartir el curso, para ver el código generado, como han aplicado las soluciones, etc... Además, está todo por fases. Han añadido commits por sesión, etc...

La organización en capas con un servicio conductor por caso de uso, y las arquitecturas de IA que solo componen a través de él ([ADR 0001](docs/decisions/0001-stack-and-project-structure.md)).

**Prompt 3:**

> Hemos creado summaries de todas las sesiones del master. Lo que quiero es que analices si el proyecto final de master está alineado con los requerimientos de cada sesión para tener en cuenta en este proyecto final. Muestra todo lo que esté alineado y lo que no. Sobre el análisis final realizaremos los ajustes necesarios o tomaremos las decisiones necesarias

Un análisis de 221 puntos contra las 15 sesiones y diez decisiones aprobadas, entre ellas un modelo por papel, el agente como grafo de LangGraph con pausa humana, las evaluaciones fuera del pipeline de despliegue y el endurecimiento para un despliegue público.

### **2.2. Descripción de componentes principales:**

**Prompt 1:**

> /codely-plan-create-github https://github.com/alexgraupera/AI4Devs-finalproject-AG/issues/1

El plan de la revisión de anuncios (CAG) en cinco fases: esqueleto, revisión de extremo a extremo (prompts versionados, wrapper de LLM, conductor), guardrails, fallback y coste, y caché exacta.

**Prompt 2:**

> /codely-plan-create-github https://github.com/alexgraupera/AI4Devs-finalproject-AG/issues/2

El plan RAG: almacén vectorial y migraciones, ingesta del BOE, troceo, embeddings y recuperación, respuestas con citas verificables, banco de recuperación, técnicas avanzadas medidas y control de alucinaciones.

**Prompt 3:**

> /codely-plan-create-github https://github.com/alexgraupera/AI4Devs-finalproject-AG/issues/3

El plan del agente: el bucle escrito a mano con function calling, la reescritura del anuncio, actor-crítico-jefe, el grafo de LangGraph, la pausa humana y los permisos mínimos con auditoría.

### **2.3. Descripción de alto nivel del proyecto y estructura de ficheros**

**Prompt 1:**

> Antes de continuar. Mi proyecto lo hice desde 0. Cumple con el formato que requiere el proyecto de AI4Devs-finalproject? Si no es así, adaptemos lo que es requerido con el formato requerido

El README y este `prompts.md` se adaptaron a la plantilla oficial, con las secciones 🆕 del proyecto de AI Engineering.

**Prompt 2:**

> Otra cosa. Está bien documentarlo todo, pero esto lo evaluará alguien, supongo. Estoy ayudándome de la IA (de ti) pero no tiene que parecer que estamos haciendo una copia exacta de cosas del curso. Está bien basarnos y tener las directrices y lo que vamos a implementar alineadamente con lo impartido, pero no hace falta meter comentarios de tipo "he seguido lo mismo que hay en el repositorio del master"

La documentación explica cada decisión por sus razones y sus medidas, no por su origen.

### **2.4. Infraestructura y despliegue**

**Prompt 1:**

> Otro punto que me preocupa, y no sé si habla de esto, es que no tengo presupuesto para hacerlo. Solo un poco de créditos en las apis de anthropic y openai, pero nada de infraestructura, etc... y no me gustaría gastarme mucho dinero, por no decir nada.

Infraestructura de coste cero (Render en el plan gratuito, [ADR 0021](docs/decisions/0021-hosting-on-render.md)), un tope de gasto diario en el propio servicio y el coste de cada ejecución de las evaluaciones medido y declarado.

**Prompt 2:**

> Te seré sincero. No tengo mucho tiempo ni mucha dedicación, por temas de salud y personales. Estoy intentando inferir todo lo máximo posible con lo que hago contigo y a ratos revisando contenido.
>
> En ese sentido, después de leerte, creo que lo que propones tiene sentido y voy a confiar al máximo contigo. Una vez hecho todo haremos repaso de alineación si es necesario

La forma de trabajo de la recta final: cada fase en su rama y su pull request, apiladas, con la verificación en verde y la medida en la descripción, para revisar y mergear en orden.

### **2.5. Seguridad**

**Prompt 1:**

> /codely-plan_phase-implement-github https://github.com/alexgraupera/AI4Devs-finalproject-AG/issues/2

La fase 7 del plan RAG: la verificación de que el artículo citado sostiene la respuesta, y la clave de acceso y el límite de peticiones en los endpoints ([ADR 0014](docs/decisions/0014-grounding-and-retrieval-security.md)).

**Prompt 2:**

> He gastado 10€ de api en dos días. Qué está pasando?

La revisión del gasto encontró que Anthropic había alcanzado su límite mensual y que el fallback a OpenAI seguía respondiendo sin que nadie lo notara; desde entonces cada ejecución de pago declara su coste antes y después.

### **2.6. Tests**

**Prompt 1:**

> Ya está el .env, prueba con el anuncio

La primera prueba con el modelo real, en los dos sentidos: el anuncio con tres defectos recibió las tres incidencias con la cita exacta del checklist, y uno que cumplía se aprobó sin ninguna incidencia inventada, que era el riesgo real. Los tests con el modelo simulado no podían decir ninguna de las dos cosas; desde entonces cada fase se prueba también contra el modelo real y la evidencia va en la pull request.

**Prompt 2:**

> Es **EXTREMADAMENTE IMPORTANTE** que el proyecto final siga estos dos puntos:
> 1. Debe ajustarse **totalmente** a lo impartido en el curso. [...]
> 2. Debe basarse en gran parte en el código del repositorio del master, ya que todas las sesiones se han basado en este
>
> Valida que lo cumplimos a rajatabla, que no se nos escapa nada y estamos alineados

Entre lo que se ajustó: un único comando de verificación (`make verify`: lint, tipos y tests) antes de cada commit, y tests que nunca llaman a un modelo real.

---

### 3. Modelo de Datos

**Prompt 1:**

> Quiero acabar de entender algo. El Boe, no es algo que cambie, verdad? o estoy equivocado? Quiero entender realmente porqué el cliente, si se va a llamar cada vez, etc... sobretodo por performance

El corpus se descarga una vez, se guarda versionado (`corpus.lock.json`, versión del corpus y modelo de embeddings en cada fila) y se reingiere solo cuando el BOE cambia.

**Prompt 2:**

> Quiero acabar de entender cada cuanto se ejecutaría make corpus-report y quien. Te refieres a que se descarga el contenido pero hay que tenerlo actualizado?

El workflow semanal que detecta la deriva del BOE y abre una issue cuando una norma cambia.

**Prompt 3:**

> He encontrado este repositorio que lo encuentro muy interesante. Nos serviría?
> https://github.com/legalize-dev/legalize-es

Se estudió y no se adoptó: no lleva los identificadores de bloque con los que se construye el enlace al artículo, no cubre las resoluciones de zonas tensionadas y es una obra derivada ([ADR 0009](docs/decisions/0009-chunking-strategy.md)).

---

### 4. Especificación de la API

**Prompt 1:**

> /codely-plan_phase-implement-github https://github.com/alexgraupera/AI4Devs-finalproject-AG/issues/1

La fase 2 del plan CAG: el contrato de dominio y `POST /api/v1/listings/review`, documentado en la sección 4 del README con un ejemplo de petición y de respuesta.

**Prompt 2:**

> /codely-plan_phase-implement-github https://github.com/alexgraupera/AI4Devs-finalproject-AG/issues/2

La fase 4 del plan RAG: `POST /api/v1/regulations/ask`, con citas construidas desde lo recuperado y nunca desde lo que escribe el modelo.

---

### 5. Historias de Usuario

**Prompt 1:**

> Ok, me encaja. Intentémoslo
>
> Dime los pasos que tengo que seguir. Entiendo que mejor crear un repositorio nuevo? Qué nombre, etc...
> Una vez lo tengamos, me gustaría usar las skills de codelyTv para poder elaborar el proyecto. Entiendo que necesitaremos algo, una issue inicial, lo que sea, para elaborar las issues para ir implementando, etc...

**Prompt 2:**

> Ok. Vamos por pasos. Ya he creado yo el repositorio [...]
>
> Crea las issues padre. Piensa en que esto lo validarán, por lo que debe estar orientado a cubrir los requerimientos del proyecto final, es decir, que se cumplan, y también a validar que tengo los conocimientos (o como mínimo las nociones)

Las épicas #1 a #6, una por capa de IA más evaluación, despliegue y datos reales; las tres primeras, con su historia de usuario, son las de la sección 5 del README.

**Prompt 3:**

> Ok, apruebo el plan, crea las issues

---

### 6. Tickets de Trabajo

**Prompt 1:**

> Antes de continuar con todo, quiero que valides todas las fuentes de datos que queremos utilizar en el proyecto. No quiero empezar nada y luego quedarme sin poder continuar

**Prompt 2:**

> Ok, entiendo, pero necesito la información de utilización, documentada y con ejemplos en alguna parte del proyecto, para luego poder utilizarlo

Las guías y los ejemplos ejecutables de [`docs/data-sources/`](docs/data-sources/README.md), que los tickets de ingesta citan como contrato.

**Prompt 3:**

> /codely-plan-create-github https://github.com/alexgraupera/AI4Devs-finalproject-AG/issues/3

Los tickets del agente (#38 a #44), cada uno con contratos, tests y tareas, como el de la pausa humana que resume la sección 6 del README.

---

### 7. Pull Requests

**Prompt 1:**

> En la PR #11, debes actualizar algo de la descripción de la pr?

**Prompt 2:**

> Ya la he mergeado, sigue con la fase 3

**Prompt 3:**

> Sobre lo del gasto, no es real. Me avisó con el mensaje de límite porqué no estaba reseteado. Hay unos 4,9€ de saldo aun

Las pull requests de la recta final declaran lo que costó cada medida y lo que queda de presupuesto, y prefieren ejecuciones parciales cuando bastan.
