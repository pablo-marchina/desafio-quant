"""Startup Classifier — aplica os 3 eixos AI-native.

Aplica os 3 eixos AI-native (CLAUDE.md "Conceitos de domínio") sobre os dados
estruturados (já verificados pelo Evidence Validator), via LLM com structured output.
Devolve um rótulo (ai-native | ai-enabled | non-ai) — usado pelo desvio condicional
do grafo — e a análise por eixo (rastreabilidade).

Dois reforços de robustez (esta é a decisão do desvio, vale estabilizá-la):
- **Few-shot:** o prompt traz âncoras resolvidas (Tractian=ai-native, um ai-enabled,
  um non-ai) para o modelo calibrar a fronteira, em vez de decidir só pela descrição.
- **Self-consistency:** classifica `classifier_n_votos` vezes (com temperatura > 0) e
  devolve o rótulo majoritário — reduz o ruído de uma tacada única num caso de fronteira.
"""

from collections import Counter

from app.config import settings
from app.llm import chat_structured
from app.state import Classificacao, DadosEmpresa, RadarState

_INSTRUCAO = (
    "Você classifica a maturidade 'AI-native' de uma startup em 3 eixos:\n"
    "1) Produto: a IA é o core do valor, não um feature? (teste: se remove a IA, sobra produto?)\n"
    "2) Dados e modelo: tem dado proprietário e/ou treina/serve modelo próprio, "
    "em vez de só chamar API de terceiro?\n"
    "3) Stack técnica: controla custo/latência da própria inferência (sinal forte: GPU/infra própria)?\n\n"
    "Rótulos: 'ai-native' (IA é o core nos 3 eixos), 'ai-enabled' (usa IA como "
    "feature/wrapper), 'non-ai' (não usa IA de forma relevante). Avalie só pelo "
    "texto; não invente. Responda no schema pedido."
)

# Âncoras resolvidas (few-shot): calibram onde fica a linha entre as categorias.
_EXEMPLOS = (
    "Exemplos de referência (calibre por eles):\n"
    "- Tractian — sensores IoT próprios + modelos de manutenção preditiva treinados com "
    "dado proprietário, controla a própria inferência → ai-native (referência 'nota 10').\n"
    "- CRM SaaS que chama a API da OpenAI para resumir e-mails (IA é um feature; sem "
    "modelo/dado próprio) → ai-enabled.\n"
    "- Varejo/serviço tradicional sem uso relevante de IA → non-ai."
)


def classificar(dados: DadosEmpresa) -> Classificacao:
    """Uma classificação (single-shot) com structured output e few-shot no prompt.

    Temperatura > 0 de propósito: os votos da self-consistency precisam variar; a
    maioria (ver `classificar_consistente`) compensa o ruído individual.
    """
    structured = chat_structured(Classificacao, temperature=settings.classifier_temperatura)
    prompt = f"{_INSTRUCAO}\n\n{_EXEMPLOS}\n\nDados da empresa:\n{dados.model_dump_json(indent=2)}"
    return structured.invoke(prompt)


def classificar_consistente(dados: DadosEmpresa, n: int | None = None) -> Classificacao:
    """Self-consistency: classifica `n` vezes e devolve o veredito majoritário.

    Mantém a rastreabilidade dos eixos escolhendo o primeiro voto do rótulo vencedor.
    """
    n = n or settings.classifier_n_votos
    votos = [classificar(dados) for _ in range(n)]
    vencedor = Counter(v.rotulo for v in votos).most_common(1)[0][0]
    return next(v for v in votos if v.rotulo == vencedor)


def classifier(state: RadarState) -> dict:
    dados = state.dados_estruturados or DadosEmpresa(nome=state.consulta)
    # se nada foi coletado (ex.: busca bloqueada), não dá para classificar:
    # rotular honestamente como "sem-dados" em vez de chutar "non-ai".
    if not (dados.setor or dados.descricao or dados.tecnologias):
        return {"classificacao": "sem-dados"}
    c = classificar_consistente(dados)
    return {"classificacao": c.rotulo, "classificacao_detalhe": c}
