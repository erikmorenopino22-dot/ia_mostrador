# La IA de Mostrador: qué es y cómo entrenarla con datos del centro

## Qué es hoy

La IA de Mostrador es **propia del centro**: se crea en el ordenador servidor, se llama `mostrador`, tiene su identidad y sus normas (definidas en `app/ia_propia.py`) y funciona sin conexión a ningún servicio externo. No usa Claude, ChatGPT ni ninguna otra IA comercial.

Por dentro se construye sobre un **modelo de lenguaje de pesos abiertos** (Gemma 3, de Google, por defecto), que se descarga una vez y queda en el equipo. Es lo que hacen prácticamente todos los proyectos de IA propia: entrenar un modelo de lenguaje desde cero cuesta millones de euros en cálculo y billones de palabras de texto, algo fuera del alcance de cualquier centro educativo. Lo que sí está al alcance es el paso siguiente: **ajustar ese modelo abierto con los datos del propio centro**, para que aprenda a valorar como valora vuestro profesorado. Esta guía explica cómo.

Puedes comprobar que la IA está creada abriendo una terminal y escribiendo `ollama list`: aparecerá `mostrador`. Con `ollama run mostrador` puedes hablar con ella directamente.

## Por qué entrenarla

Ahora mismo la IA valora siguiendo las rúbricas, pero no conoce el criterio concreto del equipo docente: qué se considera "en parte", qué detalles se penalizan, cómo se explica el feedback. Cada vez que una profesora revisa una práctica y corrige la propuesta de la IA, se genera justo el ejemplo que hace falta para enseñárselo. Con unos cientos de prácticas revisadas, el ajuste fino suele acercar mucho la IA al criterio del centro.

## Paso 1: reunir prácticas revisadas

Usad Mostrador con normalidad y **revisad las entregas poniendo la nota**. Solo cuentan las prácticas en estado *Revisada*. Para un primer entrenamiento útil conviene tener **300 o más**, de casos variados. Es buena idea dejar aparte un 20 % para comprobar después si la IA ha mejorado.

## Paso 2: exportar los datos

Con Mostrador cerrado, en una terminal dentro de la carpeta del programa:

```
.venv/bin/python -m scripts.exportar_entrenamiento        (Linux / Mac)
.venv\Scripts\python -m scripts.exportar_entrenamiento    (Windows)
```

Se crea la carpeta `datos_entrenamiento` con:

- `valoracion.jsonl`: cada práctica con su rúbrica, y como respuesta correcta **la nota que puso el profesorado**. Es el conjunto más valioso.
- `cliente.jsonl`: las conversaciones con el cliente simulado.
- `resumen.txt`: cuántos ejemplos hay y **cuánto coincide hoy la IA con el profesorado**. Guarda esta cifra para compararla después del entrenamiento.

Los datos salen anonimizados (sin alias, grupos ni identificadores), pero **revísalos antes de usarlos**: un alumno puede haber escrito datos personales en un mensaje.

## Paso 3: entrenar (ajuste fino con LoRA)

El ajuste fino se hace con herramientas libres como [Unsloth](https://github.com/unslothai/unsloth) o [Axolotl](https://github.com/axolotl-ai-cloud/axolotl), que aceptan directamente el formato de `valoracion.jsonl`. La técnica recomendada es **LoRA**: en lugar de reentrenar todo el modelo, se entrena una pequeña capa encima, lo que reduce mucho la memoria y el tiempo necesarios.

Orientativamente:

| Modelo base | Tarjeta gráfica necesaria para entrenar | Tiempo con 300-1000 ejemplos |
|---|---|---|
| Gemma 3 4B | 12-16 GB | Menos de una hora |
| Gemma 3 12B | 24 GB | Una o pocas horas |

Parámetros razonables para empezar: 2 o 3 épocas, rango LoRA 16, tasa de aprendizaje 2e-4, contexto de 4096 tokens.

**Dónde entrenar.** Lo ideal es un equipo del centro con tarjeta gráfica, para que los datos no salgan. Si se usa un servicio en la nube, los datos del alumnado salen del centro: hay que consultarlo antes con el delegado o delegada de protección de datos.

Es un proyecto muy adecuado para el alumnado del ciclo de **Desarrollo de Aplicaciones Web** o de un curso de especialización en IA, con el profesorado de Farmacia aportando el criterio.

## Paso 4: cargar el modelo entrenado

Al terminar, exporta el modelo en formato **GGUF** (Unsloth lo hace con `save_pretrained_gguf`, cuantización `q4_k_m`). Junto al archivo `.gguf` suele generar un `Modelfile`; si no, crea uno con esta línea:

```
FROM ./mostrador-ajustado.gguf
```

En el ordenador servidor, en la carpeta donde estén esos archivos:

```
ollama create mostrador-base-v2 -f Modelfile
```

Abre el archivo `.env` de Mostrador y cambia:

```
IA_MODELO_BASE=mostrador-base-v2
```

Al volver a abrir Mostrador con el lanzador, la IA `mostrador` se reconstruye automáticamente sobre el modelo entrenado, con la misma identidad y normas.

## Paso 5: comprobar que ha mejorado

Pasa por la nueva IA las prácticas que dejaste aparte, revísalas y vuelve a exportar: la cifra de **coincidencia con el profesorado** de `resumen.txt` debería subir. Si no sube, normalmente faltan ejemplos o son poco variados. Si empeora, basta con volver a poner el modelo base anterior en `.env`.

## Licencias

El modelo entrenado es un derivado del modelo base y sigue sujeto a su licencia (en el caso de Gemma, sus condiciones de uso, que permiten este uso educativo). Los datos de entrenamiento son del centro.
