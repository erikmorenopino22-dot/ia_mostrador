# Instalar Mostrador en un ordenador del centro

Esta guía es para cualquier persona del centro, sin conocimientos técnicos. Mostrador se instala en **un solo ordenador**, que hace de servidor. El alumnado y el profesorado lo usan desde el navegador de sus propios equipos, tablets o móviles, siempre que estén conectados a la **misma red** (la wifi o la red del aula).

Mostrador tiene **su propia IA**, que se crea en ese ordenador y funciona dentro de él: **no depende de ninguna IA comercial, no necesita internet para usarse, no tiene coste por uso y las conversaciones no salen del centro.** Solo hace falta internet la primera vez, para descargar los programas y el modelo abierto sobre el que se construye. Cómo es esa IA y cómo entrenarla con los datos del centro se explica en `ENTRENAR_IA.md`.

## Qué ordenador hace falta

La IA es lo que más recursos consume. Elige el modelo según el equipo:

| Equipo | Modelo recomendado | Para cuánta gente a la vez |
|---|---|---|
| Sin tarjeta gráfica, 16 GB de RAM | `gemma3:4b` | 2 o 3 personas. Respuestas de 10 a 30 segundos |
| Tarjeta gráfica con 12 a 16 GB, o Mac con chip M y 16 GB o más | `gemma3:12b` (el que viene por defecto) | Un grupo entero, con alguna espera |
| Tarjeta gráfica con 24 GB | `gemma3:27b` | Un grupo entero, con más calidad |

Además, unos 20 GB libres en el disco (13 GB con el modelo por defecto, más margen para copias y datos).

Antes de usarlo con una clase entera, mide si el equipo aguanta con la **prueba de carga** (ver *Comprobar que el equipo aguanta una clase*).

Para cambiar de modelo, abre el archivo `.env` de la carpeta de Mostrador con el Bloc de notas y cambia la línea `IA_MODELO_BASE`. La próxima vez que lo abras, se descargará y la IA de Mostrador se reconstruirá sobre él.

## Instalación (solo la primera vez)

**1. Instala Ollama**, el motor libre que ejecuta la IA en el equipo. Descárgalo de https://ollama.com/download e instálalo como cualquier otro programa. En Linux (por ejemplo LliureX) se instala escribiendo en una terminal:

```
curl -fsSL https://ollama.com/install.sh | sh
```

**2. Instala Python** si el equipo no lo tiene.

- **Windows:** descárgalo de https://www.python.org/downloads/. En la primera pantalla del instalador, **marca la casilla "Add python.exe to PATH"**.
- **Mac:** descárgalo de la misma página.
- **Linux / LliureX:** escribe `sudo apt install python3 python3-venv`.

**3. Descomprime la carpeta de Mostrador** donde quieras, por ejemplo en Documentos.

**4. Ábrelo:**

- **Windows:** doble clic en `Iniciar Mostrador.bat`.
- **Mac:** doble clic en `Iniciar Mostrador.command`. Si el Mac no te deja, haz clic derecho sobre el archivo y elige *Abrir*.
- **Linux:** abre una terminal en la carpeta y escribe `./iniciar.sh`.

La primera vez tarda bastante, porque instala lo necesario, descarga el modelo abierto de base (varios GB) y crea sobre él la IA de Mostrador. Las siguientes veces arranca en unos segundos.

**5. Crea la cuenta del profesorado.** Cuando termina, se abre el navegador con la pantalla *Configura Mostrador*. Te pide un **código de configuración** que aparece en la ventana negra (y en el archivo `CODIGO_CONFIGURACION.txt` de la carpeta). Escríbelo junto con tu nombre, tu correo y una contraseña. Ese código solo sirve una vez.

Si Windows pregunta si quieres permitir el acceso a la red, elige **Permitir** en **redes privadas**. Si no, el alumnado no podrá conectarse.

## Uso diario

1. Enciende el ordenador servidor y abre Mostrador con doble clic. **No cierres la ventana negra** mientras se use: es el servidor.
2. En la pestaña *Grupos* verás la **dirección para el alumnado**, del estilo `http://192.168.1.25:8000`. Escríbela en la pizarra.
3. Crea un grupo para cada clase. Cada grupo tiene un código de 6 caracteres.
4. El alumnado abre esa dirección en su navegador, elige *Soy alumno/a* y entra con el código del grupo, un alias y un PIN que elige la primera vez.
5. Para dar acceso a otro profesor o profesora, en *Grupos*, abajo, pulsa *Dar acceso a otra profesora o profesor*.

## Si algo no funciona

**El alumnado no puede abrir la dirección.** Comprueba que están en la misma red que el ordenador servidor. Algunas wifis de centros aíslan los dispositivos entre sí: si es el caso, pide al coordinador TIC que permita las conexiones al puerto 8000 de ese equipo, o conecta el servidor por cable a la red del aula. Revisa también el cortafuegos de Windows (permitir Python en redes privadas).

**La dirección cambia de un día para otro.** El router asigna la dirección del servidor. Pide al coordinador TIC que le reserve una fija.

**"La IA de Mostrador no está en marcha".** Cierra Mostrador y vuelve a abrirlo con el lanzador. Si sigue igual, abre Ollama desde el menú de aplicaciones.

**Las respuestas tardan mucho.** El equipo va justo para el modelo o hay mucha gente a la vez. Prueba con `gemma3:4b`, o usa un equipo con tarjeta gráfica.

**"El puerto 8000 ya está en uso".** Mostrador ya está abierto en otra ventana. Si no, cambia `PUERTO` en el archivo `.env`.

**Alguien ha olvidado su PIN.** En *Grupos* > *Ver alumnado* puedes ponerle uno nuevo.

## Comprobar que el equipo aguanta una clase

Con Mostrador abierto, abre una terminal en su carpeta y escribe (con tu correo de profesor):

```
.venv\Scripts\python -m scripts.prueba_carga --email tu@correo.es      (Windows)
.venv/bin/python -m scripts.prueba_carga --email tu@correo.es          (Linux / Mac)
```

Simula a 25 alumnos practicando a la vez durante unos minutos, en un grupo temporal que se borra solo al terminar. El resultado dice **BIEN**, **ACEPTABLE** o **INSUFICIENTE** para las respuestas del cliente y para la valoración, y se guarda en un archivo `prueba_carga_….txt`. Para otro tamaño de grupo, añade `--alumnos 15`. Hazla fuera del horario de clase: durante la prueba el servidor va cargado.

## Copias de seguridad y actualizaciones

Todo lo importante (cuentas, grupos, casos y prácticas) está en el archivo **`mostrador.db`**. Mostrador hace **una copia automática al día** mientras está abierto, en la carpeta `copias`, y conserva las 30 más recientes. En la pestaña *Grupos* se ve la fecha de la última copia y hay un botón para hacer una en el momento.

Esas copias están en el mismo ordenador: si el disco se estropea, se pierden con él. Copia la carpeta `copias` a otro sitio de vez en cuando (un disco externo o una unidad de red del centro), o cambia `COPIAS_CARPETA` en `.env` para que se guarden directamente en otro disco.

**Para recuperar una copia:** cierra Mostrador, renombra `mostrador.db` (por si acaso), copia el archivo de la copia que quieras a la carpeta de Mostrador con el nombre `mostrador.db` y vuelve a abrirlo.

**Al acabar el curso**, cierra cada grupo y pulsa *Eliminar grupo y sus datos*: borra el alumnado y todas sus prácticas. Ten en cuenta que siguen existiendo en las copias de seguridad hasta que estas se renuevan (30 días por defecto).

Para actualizar a una versión nueva, sustituye los archivos de la carpeta **pero conserva `mostrador.db` y `.env`**. Si la versión nueva cambia las librerías, borra la carpeta `.venv` y se reinstalarán solas al abrirlo.

## Calidad de la IA local

Un modelo que cabe en un ordenador normal es menos preciso que los grandes modelos en la nube. En la práctica:

- Interpreta bien al cliente en castellano. En valenciano funciona, pero con más errores.
- La valoración automática es más irregular. Por eso es solo una propuesta y la nota siempre la pone el profesorado: revisa las entregas antes de dar la nota por buena.
- Los casos deben revisarlos docentes del ciclo antes de publicarlos.

La forma de mejorarla es entrenarla con las prácticas que el profesorado ya ha revisado, o usar un modelo base más grande si el equipo lo permite. Ambas cosas se explican en `ENTRENAR_IA.md`.
