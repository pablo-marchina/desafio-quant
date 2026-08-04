import argparse
import os
import sys

from groq import Groq

from rag.catalog import category_names, detect_services, service_names
from rag.retrieval.search import search
from rag.settings import required_env

CHAT_MODEL = os.getenv("GROQ_CHAT_MODEL", "openai/gpt-oss-120b")
_client_groq: Groq | None = None

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PREAMBLE = """
Voce e um assistente especialista no catalogo de produtos e servicos NVIDIA.
Responda somente com base nos documentos recuperados fornecidos.
Caso os documentos nao sejam suficientes, diga claramente que nao ha
informacao suficiente no contexto recuperado.
Responda no idioma da pergunta, de forma objetiva e tecnicamente precisa.
Inclua citacoes no formato [Fonte N] para sustentar as afirmacoes principais.
Use exatamente o formato [Fonte N]; nunca use apenas [N].
Nao invente URLs, comandos, produtos ou detalhes tecnicos.
Nao classifique um produto como SaaS, PaaS ou IaaS sem suporte explicito nas fontes.
""".strip()


def _groq_client() -> Groq:
    global _client_groq
    if _client_groq is None:
        _client_groq = Groq(api_key=required_env("GROQ_API_KEY"))
    return _client_groq


def build_context(results: list[dict]) -> str:
    documents = []
    for index, result in enumerate(results, start=1):
        documents.append(
            f"[Fonte {index}]\n"
            f"Servicos: {', '.join(result['services'])}\n"
            f"Categorias: {', '.join(result['categories'])}\n"
            f"URL: {result['source_url']}\n"
            f"Conteudo:\n{result['text']}"
        )
    return "\n\n---\n\n".join(documents)


def generate_answer(
    question: str,
    service: str | None = None,
    category: str | None = None,
) -> tuple[str, list]:
    results = search(question, service=service, category=category)
    if not results:
        return "Nao foram encontrados documentos relevantes para responder.", []

    target_services = [service] if service else detect_services(question)
    max_completion_tokens = max(1200, 900 + 300 * len(target_services))
    response = _groq_client().chat.completions.create(
        model=CHAT_MODEL,
        messages=[
            {"role": "system", "content": PREAMBLE},
            {
                "role": "user",
                "content": (
                    f"Pergunta:\n{question}\n\n"
                    f"Documentos recuperados:\n{build_context(results)}"
                ),
            },
        ],
        temperature=0.2,
        reasoning_effort="medium",
        max_completion_tokens=max_completion_tokens,
    )
    return response.choices[0].message.content, results


def display_answer(answer: str, results: list[dict]) -> None:
    print("\n" + "=" * 70)
    print("RESPOSTA")
    print("=" * 70)
    print(answer)
    print("\nFONTES RECUPERADAS")
    for index, result in enumerate(results, start=1):
        print(f"- [Fonte {index}] {result['source_url']}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Consulta RAG do catalogo NVIDIA.")
    parser.add_argument("question", nargs="+")
    parser.add_argument("--service", choices=service_names())
    parser.add_argument("--category", choices=category_names())
    args = parser.parse_args()

    answer, results = generate_answer(
        " ".join(args.question),
        service=args.service,
        category=args.category,
    )
    display_answer(answer, results)


if __name__ == "__main__":
    main()
