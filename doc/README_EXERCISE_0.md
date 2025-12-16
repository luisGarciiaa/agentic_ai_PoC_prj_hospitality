# Exercise 0 – Asistente Agentic Simple con contexto por ficheros

## ¿Qué es este ejercicio?

En el Exercise 0 el objetivo no es construir un agente complejo, sino entender
cómo funciona un **agente mínimo** que responde preguntas usando información
cargada directamente en el prompt del modelo.

Es un primer contacto con:

* agentes LLM
* inyección de contexto
* flujo frontend → backend → LLM
* limitaciones de este enfoque

---

## Qué hace el agente

El agente implementado (`hotel_simple_agent`) responde preguntas sobre hoteles
utilizando información que se carga desde ficheros locales.

No utiliza:

* RAG
* herramientas
* memoria
* razonamiento multi-step

Simplemente:

1. carga los datos
2. construye un prompt
3. envía el prompt y la pregunta al LLM
4. devuelve la respuesta

---

## De dónde salen los datos (esto lo probé a mano)

El agente intenta cargar los datos desde dos posibles rutas:

1. **Ruta local del servicio (Docker)**

   ```
   ai_agents_hospitality-api/data/hotels/
   ```

2. **Ruta externa (datos generados)**

   ```
   bookings-db/output_files/hotels/
   ```

Durante las pruebas comprobé que, cuando existen datos en la carpeta `data/hotels`
del servicio, **el agente usa esos datos**, no los generados en `bookings-db`.

Esto se ve claramente en los logs:

```
Using local hotel data path: /app/data/hotels
```

---

## Qué ficheros se cargan realmente

Los ficheros que se utilizan como contexto son:

* `hotels.json`
  Información estructurada de los hoteles (nombres, ciudades, precios, etc.).

* `hotel_details.md`
  Texto descriptivo largo con detalles de los hoteles.

Estos ficheros se cargan **una sola vez** y se guardan en memoria.

---

## Cacheo en memoria (comportamiento importante)

Algo que descubrí durante las pruebas es que:

* una vez que el agente carga los datos
* **ya no vuelve a leer los ficheros**
* aunque se modifiquen o se borren en disco

Para comprobarlo:

* moví `hotels.json` fuera del contenedor
* el agente siguió respondiendo correctamente
* hasta que reinicié el contenedor

Tras reiniciar, el agente detectó correctamente que el fichero no existía y mostró
el error correspondiente.

Conclusión:
👉 para que el agente vuelva a leer los datos es necesario reiniciar el proceso.

---

## Cómo se construye el prompt

El contexto se envía al modelo **como texto plano**, no como ficheros adjuntos.

El prompt se construye concatenando:

* el contenido completo de `hotel_details.md`
* un `json.dumps` del contenido de `hotels.json`
* la pregunta del usuario

Todo esto se incluye dentro del mensaje de sistema junto con instrucciones
sobre cómo debe responder el asistente.

No hay ningún filtrado ni selección previa del contexto.

---

## Flujo completo de una pregunta

1. El usuario escribe una pregunta en la UI web.
2. La pregunta llega al backend por WebSocket.
3. `main.py` llama a `handle_hotel_query_simple`.
4. El agente:

   * carga el contexto (si no está en memoria)
   * crea el prompt
   * llama al modelo Gemini
5. La respuesta se devuelve al frontend.

Este flujo se puede seguir fácilmente revisando los logs del contenedor.

---

## Configuración del modelo

La configuración del agente está centralizada en:

```
ai_agents_hospitality-api/config/agent_config.yaml
```

En mi caso:

* proveedor: Gemini
* modelo: `gemini-2.5-flash-lite`
* temperatura: 0

La API key se obtiene desde una variable de entorno (`AI_AGENTIC_API_KEY`),
no desde ficheros `.env`.

---

## Pruebas realizadas

### Pruebas manuales

* Preguntas desde la UI web (listado de hoteles, direcciones, precios, etc.).
* Comprobación del flujo WebSocket.
* Reinicio del contenedor para probar recarga de datos.
* Prueba de error al faltar `hotels.json`.

### Pruebas automatizadas

* Ejecución de `test_exercise_0.py`.
* Todos los tests pasaron correctamente.

---

## Limitaciones detectadas

Este enfoque tiene varias limitaciones claras:

* Se envía todo el contexto en cada pregunta.
* El número de tokens crece rápidamente.
* No escala para grandes volúmenes de datos.
* No hay control sobre qué parte del contexto se usa.
* No hay memoria entre preguntas.

Estas limitaciones justifican el uso de RAG en ejercicios posteriores.

---

## Conclusión

Este ejercicio sirve para entender cómo funciona un agente LLM básico y cuáles
son los problemas que aparecen cuando se intenta escalar este enfoque.

Es una buena base para introducir técnicas más avanzadas como recuperación de
contexto y agentes con herramientas en los siguientes ejercicios.








## 🧪 Pruebas y validaciones realizadas

Durante el Exercise 0 se han realizado pruebas manuales y automáticas para validar el funcionamiento del agente simple basado en contexto de ficheros.

### 1) Pruebas unitarias incluidas en el proyecto

Se ejecutó el script `test_exercise_0.py`, que valida el comportamiento básico del agente con distintas preguntas:

```bash
cd ai_agents_hospitality-api
python test_exercise_0.py
````

Pruebas verificadas:

* Listado de hoteles y localización
* Consulta de direcciones
* Planes de comida disponibles
* Información detallada de habitaciones

Resultado:

* ✅ 4/4 tests pasados correctamente

---

### 2) Pruebas manuales desde la UI (WebSocket)

Se probó el agente desde la interfaz web (`http://localhost:8001`) comprobando el flujo completo:

UI → WebSocket → agente → LLM → respuesta

Ejemplos de preguntas probadas:

* *“List the hotels in France”*
* *“What is the address of Obsidian Tower?”*
* *“What meal plans are available?”*
* *“Tell me the lowest price for a standard single room in Nice considering no meal plan”*

En los logs se confirmó el flujo completo:

```txt
Received from ...: {"content":"List the hotels in France",...}
Using Exercise 0 agent for query...
Processing question...
Sent response to ...
```

---

### 3) Verificación de carga de datos y rutas

Durante la depuración se comprobó qué ficheros de datos usa el agente.
Cuando existen, se prioriza la ruta local del contenedor:

```txt
Using local hotel data path: /app/data/hotels
Loading hotel data from /app/data/hotels/hotels.json
```

También se forzó un escenario de error moviendo temporalmente `hotels.json`.
El agente siguió respondiendo hasta reiniciar el contenedor, confirmando que los datos se cargan una vez y se cachean en memoria.

Tras reiniciar, el servicio detectó correctamente la ausencia de datos y mostró el aviso correspondiente en logs.

---

### 4) Comandos de depuración usados

```bash
docker logs -f ai_agents_hospitality-api
docker exec -it ai_agents_hospitality-api bash
docker restart ai_agents_hospitality-api
```

Estas pruebas confirman que el agente funciona correctamente en el escenario esperado del Exercise 0 y dejan claras sus limitaciones antes de introducir RAG en ejercicios posteriores.

```

