Copias de referencia de archivos reales de planta (usados para calibrar
`log_watcher.py` y `tracker.py`):

- `fabrics.csv`, `kova_models.csv`, `iv4_config.ini`: completos, tal cual.
- `registro_inspeccion_sample.csv`: solo las primeras 200 filas del
  archivo real (42,599 filas) -- suficiente para pruebas, sin cargar el
  archivo completo aquí.

Uso rapido para probar el modo standalone contra estos datos:

```python
from pathlib import Path
from vision_agent.config import VisionAgentConfig
from vision_agent.core import VisionAgentCore
from vision_agent.tracker import ObservedLayerCatalog
from vision_agent.log_watcher import LogWatcher

config = VisionAgentConfig.load("vision_agent_config.ini")
agent = VisionAgentCore(config, layer_catalog=ObservedLayerCatalog())
watcher = LogWatcher(agent, Path("examples/reference_data/registro_inspeccion_sample.csv"))
watcher.start()
```
