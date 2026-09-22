"""
Vision Agent -- desktop app entry point (Tkinter, matches the UX cues
from the original packages: "Seleccionar log", "Iniciar monitoreo",
"Reporte turno").

This is the STANDALONE mode -- it watches a VisionStation-style
registro_inspeccion.csv, same idea as the original VisionAgent.exe. If
you get IV4 inspector's source, call VisionAgentCore.handle_layer_event
directly from its own code instead (see examples/iv4_inspector_hook_example.py)
and you won't need this app or the log-polling delay at all.

This file is also the PyInstaller entry point -- see vision_agent.spec
and BUILD_EXE.md for turning this into VisionAgent.exe on a Windows
machine (PyInstaller cannot cross-build a Windows .exe from Linux/Mac,
so that last step has to run on Windows).
"""

from __future__ import annotations

import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from vision_agent.config import VisionAgentConfig
from vision_agent.core import VisionAgentCore
from vision_agent.log_watcher import LogWatcher
from vision_agent.tracker import LayerCatalog, ObservedLayerCatalog

APP_TITLE = "Vision Agent"


class VisionAgentApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        root.title(APP_TITLE)
        root.geometry("640x420")

        self.config: VisionAgentConfig | None = None
        self.agent: VisionAgentCore | None = None
        self.watcher: LogWatcher | None = None
        self.watcher_thread: threading.Thread | None = None
        self.log_path: Path | None = None
        self._ui_queue: queue.Queue[str] = queue.Queue()

        self._build_ui()
        self._load_default_config()
        self.root.after(200, self._drain_ui_queue)

    # -- UI ------------------------------------------------------------

    def _build_ui(self) -> None:
        pad = {"padx": 10, "pady": 6}

        top = ttk.Frame(self.root)
        top.pack(fill="x", **pad)
        ttk.Button(top, text="Seleccionar log", command=self.on_select_log).pack(side="left")
        self.log_label = ttk.Label(top, text="(sin log seleccionado)")
        self.log_label.pack(side="left", padx=10)

        mid = ttk.Frame(self.root)
        mid.pack(fill="x", **pad)
        self.toggle_button = ttk.Button(mid, text="Iniciar monitoreo", command=self.on_toggle_monitor)
        self.toggle_button.pack(side="left")
        ttk.Button(mid, text="Reporte turno", command=self.on_shift_report).pack(side="left", padx=10)

        status_frame = ttk.LabelFrame(self.root, text="Estado")
        status_frame.pack(fill="x", **pad)
        self.status_var = tk.StringVar(value="Detenido")
        ttk.Label(status_frame, textvariable=self.status_var).pack(anchor="w", padx=8, pady=4)

        log_frame = ttk.LabelFrame(self.root, text="Eventos")
        log_frame.pack(fill="both", expand=True, **pad)
        self.event_log = tk.Listbox(log_frame)
        self.event_log.pack(fill="both", expand=True, padx=4, pady=4)

    def _load_default_config(self) -> None:
        default_ini = Path("vision_agent_config.ini")
        if default_ini.exists():
            self._init_agent(default_ini)
        else:
            self._log_ui("No se encontro vision_agent_config.ini junto al ejecutable.")

    def _init_agent(self, config_path: Path) -> None:
        try:
            self.config = VisionAgentConfig.load(config_path)
            # Standalone VisionStation mode -- see tracker.ObservedLayerCatalog
            # docstring for why this differs from the IV4-inspector-hook default.
            self.agent = VisionAgentCore(self.config, layer_catalog=ObservedLayerCatalog())
            self._log_ui(f"Configuracion cargada: {config_path}")
        except Exception as exc:  # noqa: BLE001 -- surface any load error to the operator
            messagebox.showerror(APP_TITLE, f"No se pudo cargar la configuracion:\n{exc}")

    # -- actions ---------------------------------------------------------

    def on_select_log(self) -> None:
        path = filedialog.askopenfilename(
            title="Seleccionar registro_inspeccion.csv",
            filetypes=[("CSV", "*.csv"), ("Todos los archivos", "*.*")],
        )
        if not path:
            return
        self.log_path = Path(path)
        self.log_label.config(text=str(self.log_path))
        self._log_ui(f"Log seleccionado: {self.log_path}")

    def on_toggle_monitor(self) -> None:
        if self.watcher_thread and self.watcher_thread.is_alive():
            self._stop_monitor()
        else:
            self._start_monitor()

    def _start_monitor(self) -> None:
        if self.agent is None:
            messagebox.showwarning(APP_TITLE, "Primero carga vision_agent_config.ini.")
            return
        if self.log_path is None:
            messagebox.showwarning(APP_TITLE, "Primero selecciona el registro_inspeccion.csv.")
            return

        self.watcher = LogWatcher(self.agent, self.log_path)
        self.watcher_thread = threading.Thread(target=self._run_watcher, daemon=True)
        self.watcher_thread.start()
        self.toggle_button.config(text="Detener monitoreo")
        self.status_var.set(f"Monitoreando: {self.log_path.name}")

    def _run_watcher(self) -> None:
        try:
            self.watcher.start()
        except Exception as exc:  # noqa: BLE001
            self._ui_queue.put(f"Error en el monitor: {exc}")

    def _stop_monitor(self) -> None:
        if self.watcher:
            self.watcher.stop()
        self.toggle_button.config(text="Iniciar monitoreo")
        self.status_var.set("Detenido")

    def on_shift_report(self) -> None:
        if self.agent is None:
            messagebox.showwarning(APP_TITLE, "Primero carga vision_agent_config.ini.")
            return
        path = self.agent.generate_shift_report_now()
        if path:
            messagebox.showinfo(APP_TITLE, f"Reporte de turno generado:\n{path}")
        else:
            messagebox.showerror(APP_TITLE, "No se pudo generar el reporte de turno.")

    # -- thread-safe UI logging ------------------------------------------

    def _log_ui(self, message: str) -> None:
        self._ui_queue.put(message)

    def _drain_ui_queue(self) -> None:
        try:
            while True:
                message = self._ui_queue.get_nowait()
                self.event_log.insert("end", message)
                self.event_log.see("end")
        except queue.Empty:
            pass
        self.root.after(200, self._drain_ui_queue)


def main() -> None:
    root = tk.Tk()
    VisionAgentApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
