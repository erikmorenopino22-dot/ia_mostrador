# Mostrador

Simulador de atención al cliente para el ciclo de **Técnico en Farmacia y Parafarmacia**. El alumnado conversa con un cliente virtual (una IA) y, al terminar, recibe una valoración orientativa según la rúbrica que ha definido la profesora. La nota final siempre la pone la docente.

Se instala en **un ordenador del centro** y se usa desde el navegador de cualquier equipo de la misma red. Tiene **IA propia**: se crea en ese ordenador sobre un modelo de pesos abiertos y se ejecuta con [Ollama](https://ollama.com), sin depender de ninguna IA comercial, sin internet, sin coste por uso y sin que las conversaciones salgan del centro. Se puede entrenar con las prácticas revisadas del centro ([ENTRENAR_IA.md](ENTRENAR_IA.md)). El alumnado entra con un **código de grupo, un alias y un PIN**, sin cuentas externas.

**Para instalarlo, sigue [GUIA_INSTALACION.md](GUIA_INSTALACION.md).** Este README es la referencia técnica.

## Qué incluye

```
app/
  main.py            Arranque de FastAPI y servidor de la web
  config.py          Configuración (lee el archivo .env)
  models.py          Tablas: profesores, grupos, alumnos, casos, sesiones
  ia_propia.py       Identidad y parámetros de la IA de Mostrador; la crea o actualiza en el equipo
  llm.py             Uso de la IA (cliente, pistas y valoración) y versión simulada para pruebas
  routers/inicio.py  Estado, configuración inicial desde el navegador y alta de profesorado
  prompts.py         Todos los textos que se envían a la IA, en un solo sitio
  limites.py         Límite diario de mensajes y bloqueo tras intentos fallidos
  routers/           Endpoints de la API
static/              Interfaz web (HTML + JS, sin compilación) y fuentes incluidas
iniciar.py           Lanzador: crea .env, arranca el motor de IA, prepara la IA propia y abre el navegador
Iniciar Mostrador.bat / .command, iniciar.sh   Lanzadores de doble clic (Windows / Mac / Linux)
seed/casos.json      9 casos de ejemplo con sus rúbricas
scripts/preparar_ia.py            Prepara la IA propia sin abrir la aplicación (Docker)
scripts/exportar_entrenamiento.py Exporta las prácticas revisadas para entrenar la IA
scripts/             Crear cuentas de profesorado y cargar casos
tests/               Pruebas automáticas (usan la IA simulada)
```

## Ejecutarlo

**Uso normal:** doble clic en el lanzador de tu sistema (ver la guía de instalación). Al arrancar por primera vez se cargan los casos de ejemplo y se genera un código de configuración para crear la primera cuenta de profesorado desde el navegador.

**Desarrollo:**

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env            # LLM_PROVIDER=fake para probar sin IA
uvicorn app.main:app --reload
pytest
```

**Servidor con Docker:** `docker-compose.yml` levanta Mostrador, Ollama y PostgreSQL. Las instrucciones están al principio del archivo. Para exponerlo fuera de la red local hace falta ponerlo detrás de HTTPS.

## La IA propia

Al arrancar, el lanzador descarga el modelo base (`IA_MODELO_BASE`, por defecto `gemma3:12b`) y crea sobre él, mediante la API de creación de modelos de Ollama, la IA `mostrador` (`IA_NOMBRE`) con su identidad y sus parámetros, definidos en `app/ia_propia.py`. Si la identidad o la base cambian, la reconstruye; si no, la deja como está. `python -m scripts.preparar_ia --modelfile` la muestra en formato Modelfile.

Toda la aplicación usa solo esa IA. La valoración se pide con salida JSON restringida a un esquema (`ESQUEMA_VALORACION` en `prompts.py`) y se reintenta una vez si el modelo no lo respeta. Para atender varias peticiones a la vez, el lanzador arranca Ollama con `OLLAMA_NUM_PARALLEL=4`.

Para que la IA aprenda el criterio del centro, `scripts/exportar_entrenamiento.py` genera datos de ajuste fino a partir de las notas del profesorado; el modelo entrenado se carga como nueva base. El proceso está en [ENTRENAR_IA.md](ENTRENAR_IA.md). Para pruebas sin IA existe `LLM_PROVIDER=fake`.

## Cómo se usa

1. La profesora entra con su correo y contraseña y crea un **grupo** (por ejemplo, "1º Farmacia A"). Se genera un código de 6 caracteres.
2. Comparte el código con la clase. Cada alumno entra con el código, un alias y un PIN que elige la primera vez. Si alguien olvida el PIN, la profesora lo cambia desde la pestaña Grupos.
3. El alumnado practica los casos publicados. Al terminar, recibe la valoración orientativa de la IA.
4. La profesora revisa las entregas, ve la conversación completa y la propuesta de la IA, y pone la nota criterio por criterio con un comentario.
5. Al acabar el curso, puede **cerrar el grupo** para que nadie más pueda entrar con ese código.

## Privacidad y marco legal

El diseño sigue el principio de minimización de datos del RGPD. Del alumnado solo se guarda un alias y un PIN cifrado: ni correo, ni DNI, ni información sobre necesidades educativas. Las adaptaciones de lectura (tamaño de letra, tipografía, voz) se guardan solo en el navegador de cada alumno y nunca llegan al servidor, así que nadie tiene que declarar una necesidad para beneficiarse de ellas.

Aun así, hay que tener en cuenta lo siguiente antes del uso real:

- El centro debe informar al alumnado (y a las familias de los menores de edad) del tratamiento de datos y valorarlo con su delegado o delegada de protección de datos. Conviene recomendar que el alias no sea el nombre completo.
- La IA se ejecuta en el ordenador del centro: las conversaciones no se envían a ningún servicio externo.
- Los datos exportados para entrenar la IA salen anonimizados, pero hay que revisarlos, y no deben salir del centro sin consultarlo con protección de datos.
- La valoración de la IA es una **propuesta**: la nota la decide siempre la profesora. Es una decisión de diseño deliberada, porque el Reglamento Europeo de IA considera de alto riesgo los sistemas que evalúan resultados de aprendizaje de forma autónoma.
- Los casos tratan contenido sanitario. Deben revisarlos docentes del ciclo antes de publicarlos, y la IA está instruida para no dar consejos como si fuera farmacéutica.

## Copias de seguridad

Con SQLite, `app/copias.py` hace una copia en caliente (API de backup de SQLite, con comprobación de integridad) al arrancar si la última tiene más de `COPIAS_HORAS` horas, y lo comprueba cada hora; conserva `COPIAS_CONSERVAR` copias en `COPIAS_CARPETA`. `POST /api/copias` hace una en el momento. Con PostgreSQL (Docker) no se activan: programa `docker compose exec db pg_dump -U mostrador mostrador > copia.sql` con cron.

## Prueba de carga

`python -m scripts.prueba_carga --email <profe>` simula N alumnos (`--alumnos`, 25 por defecto) que entran, practican `--mensajes` turnos con una pausa media de `--pausa` segundos y piden la valoración, en un grupo temporal que se borra al terminar. Informa del percentil 50 y 90 de cada tipo de petición, con un veredicto según umbrales (respuesta del cliente: 8 s / 20 s; valoración: 45 s / 90 s) y guarda el informe en un archivo.

## Límites

`LIMITE_DIARIO_ALUMNO` fija cuántas llamadas a la IA puede hacer cada alumno al día (150 por defecto) y cada práctica admite como máximo 60 mensajes. Con la IA local no hay coste, pero el límite evita que una sola persona sature el equipo. Los límites se guardan en memoria y se reinician al cerrar Mostrador.

## Resumen de la API

| Método | Ruta | Quién | Para qué |
|---|---|---|---|
| GET | `/api/estado` | Público | Si falta configurar, estado de la IA y dirección en la red |
| POST | `/api/configuracion-inicial` | Primer arranque | Crear la primera cuenta con el código de configuración |
| GET/POST | `/api/profesores` | Profesorado | Ver y dar de alta profesorado |
| POST | `/api/profe/login` | Profesorado | Iniciar sesión |
| POST | `/api/alumno/entrar` | Alumnado | Entrar con código, alias y PIN |
| GET/POST | `/api/grupos` | Profesorado | Ver y crear grupos |
| POST | `/api/grupos/{id}/activo?activo=` | Profesorado | Cerrar o reabrir un grupo |
| GET | `/api/grupos/{id}/alumnos` | Profesorado | Ver el alumnado de un grupo |
| POST | `/api/alumnos/{id}/pin` | Profesorado | Cambiar el PIN de un alumno |
| GET | `/api/casos` | Ambos | Listar casos (el alumnado no recibe la ficha oculta del cliente) |
| POST/PUT/DELETE | `/api/casos[/{id}]` | Profesorado | Crear, editar y borrar casos |
| POST | `/api/sesiones` | Alumnado | Empezar una práctica |
| POST | `/api/sesiones/{id}/mensajes` | Alumnado | Enviar un mensaje al cliente |
| POST | `/api/sesiones/{id}/pista` | Alumnado | Pedir una pista |
| POST | `/api/sesiones/{id}/terminar` | Alumnado | Terminar y obtener la valoración de la IA |
| GET | `/api/sesiones[/{id}]` | Ambos | Ver prácticas |
| GET | `/api/entregas?estado=&grupo_id=` | Profesorado | Listar entregas de sus grupos |
| PUT | `/api/sesiones/{id}/nota` | Profesorado | Poner la nota final |
| DELETE | `/api/grupos/{id}` | Profesorado | Borrar un grupo cerrado con su alumnado y prácticas |
| POST | `/api/copias` | Profesorado | Hacer una copia de seguridad en el momento |

## Próximos pasos sugeridos

- Mostrar la respuesta del cliente mientras se escribe (streaming): con IA local es lo que más mejoraría la sensación de espera.
- Empaquetar un instalador de Windows (.exe) que incluya Python, para no tener que instalarlo aparte.
- Migraciones de base de datos con Alembic en lugar de `create_all`, antes de publicar versiones que cambien las tablas.
- HTTPS en la red local para un uso amplio (ahora las contraseñas viajan sin cifrar por la wifi).
- Exportar las notas a CSV para pasarlas al cuaderno del profesorado.
- Integración con Aules mediante LTI, para que el alumnado entre desde el aula virtual sin otro código.
- Casos con imágenes (una receta, un prospecto, una caja de medicamento) usando la entrada de imágenes del modelo.
