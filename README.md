# Vision Agent (reconstrucción en Python)

Reimplementación en Python de las capacidades de `VisionAgent.exe`
(release "SWATCH DATASET", 2026-09-11), pensada para integrarse
directamente dentro de **IV4 inspector** en vez de correr como programa
separado.

No se contó con el código fuente de ninguno de los dos proyectos. Lo que
hay aquí se reconstruyó a partir de:

- Los **metadatos internos de `VisionAgent.exe`** (es un ejecutable .NET
  sin ofuscar: nombres de clases, métodos, propiedades, los encabezados
  literales de los 6 CSV que genera, el CSS/HTML de los reportes, y el
  regex de número de parte de tela quedaron legibles dentro del binario).
- `CHANGELOG.txt` y `LEAME.txt` de Vision Agent (comportamiento y flujo).
- `CHANGELOG.md` de IV4 inspector (flujo de secuencia, autoswitch,
  catálogos de modelo/programa, formato de QR).

## Qué es fiel al original vs. qué es aproximado

**Fiel (verificado contra el binario, no adivinado):**
- Los 6 encabezados de CSV, carácter por carácter (`storage.py`).
- El regex de número de parte: `\d{2}-\d{6,7}-\d{4}` (`qr_utils.py`).
- Los textos de recomendación exactos (`stats.py`).
- El CSS/HTML de los reportes por orden y por turno (`report.py`,
  `shift_report.py`).
- Los horarios de turno: Turno 1 06:00–16:00, Turno 2 16:00–01:00
  (`shift_schedule.py`).
- La arquitectura de clases (mismos nombres: `VisionAgentCore`,
  `ProductTracker`, `SwatchCatalog`, `FabricImageClassifier`,
  `LocalStatisticalModel`, `ShiftReportGenerator`...).

**Aproximado y marcado con `# APPROXIMATION` en el código** (la lógica
IL de un binario compilado no queda en texto plano, así que esto no se
pudo extraer, solo los nombres):
- La fórmula exacta de la firma de color/brillo/contraste y su umbral de
  distancia (`swatch.py`, `fabric_classifier.py`).
- El mapeo modelo → número de capas requeridas (`tracker.py`) — cruzar
  contra `config/model_program_matrix.csv` real de IV4 inspector en
  cuanto lo tengas.
- El formato exacto de columnas de `registro_inspeccion.csv`
  (`log_watcher.py`) — **esto es lo único que de verdad necesita una
  muestra real** para no ser un placeholder.

Ninguna de estas aproximaciones afecta el **formato de salida** (los CSV
y HTML son idénticos en estructura); solo afectan qué tan sensible es la
detección de mismatch/baja confianza, algo que de cualquier forma habría
que calibrar con datos reales de planta incluso si tuviéramos el código
original.

## Novedades de esta entrega

- **Esquemas confirmados contra datos reales de planta** (`fabrics.csv`,
  `kova_models.csv`, `registro_inspeccion.csv` de 42,599 filas reales,
  `iv4_config.ini`). Ya no son aproximaciones de la primera versión:
  - `log_watcher.py` ahora parsea el formato REAL de VisionStation:
    `Timestamp,Código,Modelo,Cushion,Capa,Programa,Resultado`, incluyendo
    el resultado `PW_ERR` (mapeado a `SYSTEM_ERROR`).
  - `tracker.py` puede cargar el `kova_models.csv` real
    (`ss_code,model_name,required_fabrics`) para inferir capas
    requeridas cuando se integra con IV4 inspector.
  - **Importante:** ese `kova_models.csv` es un concepto de **FabricVision**
    (pases de tela por modelo), no el mismo `Capa` que usa
    `registro_inspeccion.csv` de VisionStation (que solo toma valores 1
    o 2 en los datos reales). Por eso el modo standalone usa
    `tracker.ObservedLayerCatalog` en vez de `kova_models.csv` -- ver su
    docstring para el porqué.
- **Nuevo `vision_agent_inspection_time.csv`** (no existía en el
  `.exe` original): `WorkOrder, Model, Fabric, StartedAt, CompletedAt,
  ElapsedSeconds, RequiredLayers, ProductResult`. Se agregó directamente
  para el objetivo declarado del proyecto: demostrar que el tiempo de
  inspección baja, y tener en un solo lugar lo que hoy se documentaría
  a mano en SharePoint mobile scan.
- **`app.py`**: interfaz Tkinter standalone (Seleccionar log / Iniciar
  monitoreo / Reporte turno), lista para empaquetarse como `.exe`.

## Cómo obtener VisionAgent.exe

**No se puede generar el `.exe` desde este entorno de trabajo** (es
Linux, sin acceso a red, y ni PyInstaller ni tkinter están disponibles
aquí para instalarlos). Hay dos formas reales de conseguirlo, sin que
tengas que escribir código:

### Opción A -- en la nube, sin usar tu propia PC (recomendada)

Ya viene incluido `.github/workflows/build-exe.yml`. Si subes esta
carpeta a un repositorio de GitHub (puede ser privado):

1. Sube el proyecto a GitHub (`git init`, `git add .`, `git commit`,
   `git push` a un repo nuevo).
2. Entra a la pestaña **Actions** del repositorio -- el workflow
   "Build VisionAgent.exe" corre solo.
3. Cuando termine (unos 2-3 minutos), baja el artefacto
   **VisionAgent-windows** desde esa misma pantalla: ahí está el `.exe`
   real, compilado en una máquina Windows de GitHub, sin que tú
   necesites una.

### Opción B -- en una PC con Windows

1. Copia esta carpeta a una PC Windows con Python 3.10+ instalado.
2. Corre `build_windows.bat` (instala dependencias + PyInstaller y
   compila `vision_agent.spec`).
3. El resultado queda en `dist\VisionAgent\VisionAgent.exe`.
4. Copia junto al `.exe`: `vision_agent_config.ini`, `swatches\`,
   `fabric_part_images\`, y (si vas a correr contra IV4 inspector)
   `kova_models.csv`.

## Instalación (para correrlo con Python, sin compilar el .exe)

```bash
pip install -r requirements.txt
```


## Dos formas de usarlo

### 1. Integrado directamente en IV4 inspector (recomendado)

```python
from vision_agent.config import VisionAgentConfig
from vision_agent.core import VisionAgentCore

config = VisionAgentConfig.load("vision_agent_config.ini")
agent = VisionAgentCore(config)

# Una sola llamada por cada resultado de capa que IV4 inspector reciba:
outcome = agent.handle_layer_event(
    work_order="3292655",
    model="ARMLESS",
    fabric_raw="2011_FS33SBP_Mocha_Performance_Boucle_BTO_3292655.3.1.x.2",
    layer=1,
    program="P000",
    result="OK",
    screenshot=layer_screenshot,  # PIL.Image que IV4 inspector ya capturó
)
```

Ver `examples/iv4_inspector_hook_example.py` para el punto de enganche
completo. Esta es la razón principal para combinar ambos: IV4 inspector
ya sabe el instante exacto de cada evento (incluye el readback `PR` del
programa activo desde su v0.14.4), así que no hace falta adivinar
`capture_delay_ms` ni volver a tomar captura de pantalla.

### 2. Standalone (como el .exe original, vigilando un log)

Si todavía no tienes el hook directo:

```python
from pathlib import Path
from vision_agent.config import VisionAgentConfig
from vision_agent.core import VisionAgentCore
from vision_agent.log_watcher import LogWatcher

config = VisionAgentConfig.load("vision_agent_config.ini")
agent = VisionAgentCore(config)
watcher = LogWatcher(agent, Path("registro_inspeccion.csv"))
watcher.start()  # bloqueante; correr en su propio hilo/proceso
```

⚠️ `log_watcher.parse_inspection_record` usa un orden de columnas de
**marcador de posición** (no hay muestra real de
`registro_inspeccion.csv`). Ajusta esa función en cuanto tengas una
muestra real del log.

## Qué falta para una integración 1:1 con IV4 inspector

1. **Una muestra de `registro_inspeccion.csv`** (aunque sean 5 líneas) —
   para el modo standalone, o para confirmar el orden de campos si al
   final decides no usar el hook directo.
2. **`config/model_program_matrix.csv` real** de IV4 inspector, para
   reemplazar el mapeo aproximado en `tracker.py`.
3. Las carpetas **`swatches/`** y **`fabric_part_images/`** con su
   `manifest.csv` (las que ya tienes en planta) — cópialas junto a
   `vision_agent_config.ini` cuando despliegues.
4. Si en algún momento consigues el código fuente de cualquiera de los
   dos proyectos, dímelo: en ese punto conviene reemplazar las piezas
   `# APPROXIMATION` por la lógica real en vez de mantener esta
   reconstrucción.

## Estructura del paquete

```
vision_agent/
  config.py             VisionAgentConfig (lee vision_agent_config.ini)
  qr_utils.py           parseo de QR/etiqueta, extracción de PN/tela/OT
  visual_features.py    brillo/contraste/ratios locales (sin YOLO/API/internet)
  swatch.py             validación contra swatches/<tela>.jpg
  fabric_classifier.py  clasificación de PN contra fabric_part_images/<PN>/
  tracker.py            estado de producto por orden de trabajo (capas, yield)
  stats.py              modelo estadístico local + recomendaciones
  shift_schedule.py     Turno 1 / Turno 2
  storage.py            escritura de los 6 CSV (encabezados exactos)
  report.py             reporte HTML por orden (reports/WO_<orden>.html)
  shift_report.py        reporte HTML por turno
  core.py               VisionAgentCore -- orquestador y API pública
  log_watcher.py         modo standalone (vigila un log tipo CSV)
examples/
  iv4_inspector_hook_example.py
```
