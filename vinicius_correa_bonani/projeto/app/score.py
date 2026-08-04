"""Score composto.

`composto = w1·AI-Native + w2·NVIDIA-Fit + w3·Tração/VC + w4·Time-de-IA`, com as 4
notas (0–10) julgadas pelo LLM e os pesos vindos de `settings` (default) ou passados
explicitamente (o dashboard passa os pesos dos sliders e recalcula o ranking).
Função pura e determinística; aceita `Score` ou dict.
"""

from app.config import settings
from app.state import Score

EIXOS = ("ai_native", "nvidia_fit", "tracao", "time_ia")


def pesos_padrao() -> dict:
    return {
        "ai_native": settings.w_ai_native,
        "nvidia_fit": settings.w_nvidia_fit,
        "tracao": settings.w_tracao,
        "time_ia": settings.w_time_ia,
    }


def compor(notas, pesos: dict | None = None) -> float:
    """Média ponderada das 4 notas, em 0–10. `notas` pode ser um Score ou um dict.

    Os pesos são normalizados (dividido pela soma) — assim valem como pesos
    *relativos* e o score nunca estoura a escala, mesmo que os sliders da UI não
    somem 1.0. Pesos default já somam 1.0, então não muda o comportamento padrão.
    """
    p = pesos or pesos_padrao()
    get = (lambda k: getattr(notas, k)) if isinstance(notas, Score) else (lambda k: notas.get(k, 0) or 0)
    total_peso = sum(p.get(k, 0) for k in EIXOS)
    if total_peso == 0:
        return 0.0
    composto = sum(p.get(k, 0) * get(k) for k in EIXOS) / total_peso
    return round(composto, 2)
