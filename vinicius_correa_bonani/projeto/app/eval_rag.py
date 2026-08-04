"""Avaliação de qualidade do RAG (hit@k).

Mede a recuperação com um conjunto de perguntas rotuladas (pergunta → tecnologia
NVIDIA esperada). Para cada pergunta, roda `rag.recuperar` e checa se a tech
esperada aparece nos top-k (hit@k). `acertou` é função pura (testável); `avaliar`
toca o RAG real (Qdrant + Gemini + Cohere).

    python -m app.eval_rag
"""

from app import rag

# Perguntas-âncora: cada uma deve recuperar a(s) tecnologia(s) certa(s) no topo.
PERGUNTAS = [
    {"pergunta": "saúde, imagens médicas e life sciences com IA", "esperado": ["Clara", "MONAI"]},
    {"pergunta": "inferência de LLM com baixa latência em produção", "esperado": ["TensorRT-LLM", "Triton"]},
    {"pergunta": "servir modelos de IA em produção", "esperado": ["Triton", "NIM"]},
    {"pergunta": "processar grandes volumes de dados tabulares em GPU", "esperado": ["RAPIDS", "cuDF", "cuML"]},
    {"pergunta": "voz, ASR, TTS e transcrição", "esperado": ["Riva"]},
    {"pergunta": "robótica, simulação e autonomia", "esperado": ["Isaac"]},
    {"pergunta": "guardrails e governança de agentes de IA", "esperado": ["Guardrails", "NeMo"]},
    {"pergunta": "cybersecurity com IA acelerada", "esperado": ["Morpheus"]},
    {"pergunta": "microservices para deploy de modelos otimizados", "esperado": ["NIM"]},
    {"pergunta": "programa para startups, créditos e suporte técnico", "esperado": ["Inception"]},
]


def acertou(esperado: list[str], passagens: list[dict]) -> bool:
    """A tecnologia esperada aparece no título/texto dos trechos recuperados?"""
    blob = " ".join((p.get("titulo", "") + " " + p.get("texto", "")) for p in passagens).lower()
    return any(e.lower() in blob for e in esperado)


def avaliar(perguntas: list[dict] | None = None) -> dict:
    perguntas = perguntas or PERGUNTAS
    detalhes = []
    acertos = 0
    for item in perguntas:
        passagens = rag.recuperar(item["pergunta"])
        ok = acertou(item["esperado"], passagens)
        acertos += ok
        detalhes.append({"pergunta": item["pergunta"], "esperado": item["esperado"], "ok": ok})
    total = len(perguntas)
    return {"hit_rate": round(acertos / total, 2) if total else 0.0,
            "acertos": acertos, "total": total, "detalhes": detalhes}


def main() -> None:
    rel = avaliar()
    print(f"Avaliação de RAG — hit@{rag.settings.rag_top_n}: "
          f"{rel['hit_rate']}  ({rel['acertos']}/{rel['total']})\n")
    for d in rel["detalhes"]:
        marca = "✓" if d["ok"] else "✗"
        print(f"  {marca}  {d['pergunta']}  →  esperado: {', '.join(d['esperado'])}")


if __name__ == "__main__":
    main()
