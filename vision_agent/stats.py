"""
LocalStatisticalModel -- a purely local, no-ML "continuous improvement"
model: it buckets historical events by (model, fabric, layer, program)
and reports NG rate / false-positive rate for that bucket, plus a
canned recommendation when the bucket has too little history.

Recovered names: LocalStatisticalModel, StatisticalBucket, GetBucket,
GetInsight, MakeKey, Suggest, BuildRecommendation, TotalEvents,
NgRate, FalsePositiveRate, DarkRate, RedAlertRate.

The recommendation strings below are the literal text found embedded in
VisionAgent.exe (UTF-16 string table), reused verbatim so shift/order
reports read exactly like the original tool's output.
"""

from __future__ import annotations

from dataclasses import dataclass, field

MIN_BUCKET_HISTORY = 8  # APPROXIMATION: below this, "insufficient history"

RECOMMENDATIONS = {
    "insufficient_history": (
        "Historico local insuficiente: seguir recolectando datos por modelo, "
        "tela, capa y programa."
    ),
    "abnormal_event": (
        "Evento anormal: revisar acomodo de capa, tela visible, iluminacion/reflejo "
        "y posicion antes de reintentar."
    ),
    "dark_capture": "La evidencia visual se ve oscura: revisar iluminacion, sombra y posicion de la tela.",
    "red_alert": (
        "Aparecen pantallas rojas/error con frecuencia: revisar validacion de tela, "
        "lectura QR y secuencia del operador."
    ),
    "comm_error": (
        "Error de comunicacion/respuesta IV4: revisar conexion, IP/puerto y estado del Navigator."
    ),
    "swatch_mismatch": (
        "La captura se aleja del swatch esperado: validar tela fisica, iluminacion y "
        "acomodo antes de aprobar."
    ),
    "fabric_review": (
        "La tela clasifica al PN esperado, pero con baja confianza. Revisar "
        "iluminacion, enfoque y encuadre."
    ),
    "visual_mismatch": (
        "Mismatch visual de tela: validar swatch, iluminacion y que la tela fisica "
        "corresponda al QR antes de continuar."
    ),
    "ok": "Tela validada contra swatch.",
}


@dataclass
class StatisticalBucket:
    total_events: int = 0
    ng_events: int = 0
    false_positive_events: int = 0
    dark_events: int = 0
    red_alert_events: int = 0

    @property
    def ng_rate(self) -> float:
        return self.ng_events / self.total_events if self.total_events else 0.0

    @property
    def false_positive_rate(self) -> float:
        return self.false_positive_events / self.total_events if self.total_events else 0.0

    @property
    def dark_rate(self) -> float:
        return self.dark_events / self.total_events if self.total_events else 0.0

    @property
    def red_alert_rate(self) -> float:
        return self.red_alert_events / self.total_events if self.total_events else 0.0


def make_key(model: str, fabric: str, layer: int, program: str) -> str:
    return f"{model}|{fabric}|{layer}|{program}".upper()


class LocalStatisticalModel:
    def __init__(self) -> None:
        self._buckets: dict[str, StatisticalBucket] = {}

    def get_bucket(self, model: str, fabric: str, layer: int, program: str) -> StatisticalBucket:
        key = make_key(model, fabric, layer, program)
        return self._buckets.setdefault(key, StatisticalBucket())

    def update_metrics(
        self,
        model: str,
        fabric: str,
        layer: int,
        program: str,
        *,
        is_ng: bool,
        is_false_positive: bool = False,
        is_dark: bool = False,
        is_red_alert: bool = False,
    ) -> StatisticalBucket:
        bucket = self.get_bucket(model, fabric, layer, program)
        bucket.total_events += 1
        if is_ng:
            bucket.ng_events += 1
        if is_false_positive:
            bucket.false_positive_events += 1
        if is_dark:
            bucket.dark_events += 1
        if is_red_alert:
            bucket.red_alert_events += 1
        return bucket

    def get_insight(self, model: str, fabric: str, layer: int, program: str) -> tuple[StatisticalBucket, str]:
        """GetInsight: bucket + a plain-language recommendation."""
        bucket = self.get_bucket(model, fabric, layer, program)
        return bucket, self.build_recommendation(bucket)

    def build_recommendation(self, bucket: StatisticalBucket) -> str:
        if bucket.total_events < MIN_BUCKET_HISTORY:
            return RECOMMENDATIONS["insufficient_history"]
        if bucket.red_alert_rate > 0.15:
            return RECOMMENDATIONS["red_alert"]
        if bucket.dark_rate > 0.25:
            return RECOMMENDATIONS["dark_capture"]
        if bucket.ng_rate > 0.2:
            return RECOMMENDATIONS["abnormal_event"]
        return RECOMMENDATIONS["ok"]
