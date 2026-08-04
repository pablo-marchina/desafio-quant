"""Mapa de regras **gap → tech NVIDIA** (F4.1) — a base determinística do recommender (F4.2).

Converte o diagnóstico (AIMI/F2.6 + perfil) num conjunto de **techs candidatas** no formato §5.5,
ligando cada uma ao **gap que a motiva** (lado startup). É o complemento do `nvidia_rag` (F3.7):
o nó deriva os gaps em **consultas de recuperação** (busca a evidência NVIDIA); aqui os mesmos
gaps viram a **prescrição** (qual tech recomendar). O recommender (F4.2) cruza os dois — candidata
(F4.1) × citação `evidencia_nvidia` (F3.7) casadas por `kb_tech` — e produz a `Recommendation`
(F4.3) com evidência **dos dois lados** (o invariante que o Guardrails/F4.5 reforça).

**Dois eixos de regra (espelham o §5.5 e a COBERTURA):**
- `PILLAR_RULES` — o **gap do AIMI** dispara a tech que o fecha: P3 Technical Optimization →
  graduação API→stack (NIM/TensorRT-LLM/Triton — latência/throughput/"atendimento via API");
  P1 Data Moat → customização (NeMo); P2 Workflow Depth → orquestração/RAG (NeMo Retriever);
  P4 Distribution Moat → governança/enterprise (Guardrails/NeMo Evaluator/AI Enterprise).
- `SECTOR_RULES` — o **domínio** da startup acrescenta a tech de setor do §5.5: saúde→Clara/MONAI,
  voz→Riva, cyber→Morpheus, robótica→Isaac/Omniverse, simulação→Omniverse, dados tabulares→RAPIDS/
  cuDF/cuML. (Os stems parecem os de `nvidia_rag.SECTOR_QUERIES`, mas o payload é diferente — lá é
  a *query* de recuperação, aqui é a *prescrição*; o eixo "dados tabulares" é exclusivo daqui.)

**Decisão de design (espinha verde, igual F2.3–F2.7/F3):** puro, offline e determinístico — sem
rede/GPU/LLM. As justificativas/`proxima_acao` de cada regra são **esqueletos coerentes** que já
fecham o contrato §5.5 (F4.3) sem rede; o recommender Nemotron (F4.2) os **refina** com a evidência
recuperada, mas a espinha roda e é testável hoje. A seleção dos gaps reusa `gap_pillars` (F3.7) —
não há gap "recomendado" sem evidência recuperada para ele, e vice-versa (consistência gap↔tech).
`kb_tech` é o nome **exato** da tech na KB (campo `tech` do manifesto, F3.1): é a chave de junção
com a citação `evidencia_nvidia` do nó RAG, e os testes a amarram ao manifesto (mesma disciplina
do `CORE_TECHS`/F3.1 e do mapa de queries/F3.8 — adicionar uma regra com `kb_tech` inexistente
quebra o build).
"""

from __future__ import annotations

from dataclasses import dataclass

from packages.agents.nvidia_rag import gap_pillars
from packages.schemas import (
    MAX_SCORE_WITHOUT_EVIDENCE,
    AIMIPillar,
    AIMIScore,
    Classification,
    Complexity,
    Priority,
    StartupProfile,
)


@dataclass(frozen=True)
class TechRule:
    """Uma prescrição 'gap/setor → tech NVIDIA' no formato §5.5 (esqueleto determinístico).

    `kb_tech` casa com a tech do manifesto (F3.1) e com o `metadata["tech"]` da citação que o
    `nvidia_rag` (F3.7) recupera — é por ele que o recommender (F4.2) liga a prescrição à evidência
    NVIDIA. `tech` é o rótulo de produto exibido (pode refinar o componente, ex.: "NeMo Retriever"
    sob o `kb_tech` "NVIDIA NeMo"). Prioridade/complexidade são os defaults §5.5; as justificativas
    e a `proxima_acao` são esqueletos que o recommender Nemotron (F4.2) reescreve com a evidência.
    """

    kb_tech: str
    tech: str
    prioridade: Priority
    complexidade: Complexity
    justificativa_tecnica: str
    justificativa_negocio: str
    proxima_acao: str


@dataclass(frozen=True)
class SectorRule:
    """Regra de domínio (§5.5): se um `stem` casa setor/descrição do perfil, recomenda `techs`."""

    key: str
    stems: tuple[str, ...]
    techs: tuple[TechRule, ...]


@dataclass(frozen=True)
class TechCandidate:
    """Tech candidata (regra casada) + a origem do gatilho — o que o recommender (F4.2) consome.

    `pilar_origem` é o gap que a disparou (`None` = regra de setor), e vira o `pilar_origem` da
    `Recommendation` (rastreabilidade gap→tech). `triggers` lista **todas** as origens (vários gaps
    e/ou `setor:<key>`) quando a mesma tech serve a mais de um gatilho — transparência no trace.
    """

    rule: TechRule
    pilar_origem: AIMIPillar | None
    triggers: tuple[str, ...]


#: Gap (pilar do AIMI) → techs NVIDIA que o fecham, na ordem de recomendação (§5.5 / COBERTURA).
#: Apenas `kb_tech` que existem no manifesto (F3.1) — garantido por teste contra a KB.
PILLAR_RULES: dict[AIMIPillar, tuple[TechRule, ...]] = {
    # P3 — o gatilho de **graduação API→stack própria** (latência, throughput, custo, "atendimento
    # via API"): o maior upside NVIDIA e o coração do GPU Graduation Engine (F6.11).
    AIMIPillar.TECHNICAL_OPTIMIZATION: (
        TechRule(
            kb_tech="NVIDIA NIM",
            tech="NVIDIA NIM",
            prioridade=Priority.ALTA,
            complexidade=Complexity.MEDIA,
            justificativa_tecnica=(
                "Servir o modelo como NIM self-hosted substitui a dependência de API externa, "
                "trazendo latência e throughput para controle próprio (graduação API→stack)."
            ),
            justificativa_negocio=(
                "Reduz custo por token e risco de fornecedor, e constrói o moat técnico (P3) que "
                "separa uma AI-native de um wrapper."
            ),
            proxima_acao=(
                "Provisionar o NIM do modelo-alvo (build.nvidia.com → self-host na GPU) e medir o "
                "ganho contra a API atual (GPU Graduation Engine, F6)."
            ),
        ),
        TechRule(
            kb_tech="TensorRT-LLM",
            tech="TensorRT-LLM",
            prioridade=Priority.ALTA,
            complexidade=Complexity.ALTA,
            justificativa_tecnica=(
                "Compila e quantiza o LLM para a GPU, cortando latência p95 e elevando o "
                "throughput por GPU frente à inferência não otimizada."
            ),
            justificativa_negocio=(
                "Mais requisições por GPU = menor custo unitário na escala — viabiliza margem "
                "sem repassar preço ao cliente."
            ),
            proxima_acao=(
                "Compilar o modelo com TensorRT-LLM e comparar latência/throughput contra o "
                "baseline no benchmark da matriz (F6.9)."
            ),
        ),
        TechRule(
            kb_tech="NVIDIA Triton Inference Server",
            tech="NVIDIA Triton Inference Server",
            prioridade=Priority.MEDIA,
            complexidade=Complexity.MEDIA,
            justificativa_tecnica=(
                "Serving unificado com dynamic batching e multi-modelo absorve picos de carga e "
                "estabiliza a latência sob concorrência."
            ),
            justificativa_negocio=(
                "Operacionaliza a inferência otimizada em produção (observável, escalável) sem "
                "montar um servidor de modelos do zero."
            ),
            proxima_acao=(
                "Empacotar o modelo no Triton com dynamic batching e validar a latência sob carga "
                "concorrente."
            ),
        ),
    ),
    # P1 — Data Moat: dados proprietários viram diferencial via customização (data flywheel).
    AIMIPillar.DATA_MOAT: (
        TechRule(
            kb_tech="NVIDIA NeMo",
            tech="NeMo (customização + Curator)",
            prioridade=Priority.ALTA,
            complexidade=Complexity.ALTA,
            justificativa_tecnica=(
                "Customizar (fine-tuning/SFT) com dados proprietários, curados pelo NeMo Curator, "
                "fecha o data flywheel — o modelo melhora com o uso, não fica genérico."
            ),
            justificativa_negocio=(
                "Transforma o dado proprietário em moat defensável (P1): performance que um "
                "concorrente sobre API genérica não replica."
            ),
            proxima_acao=(
                "Curar um dataset proprietário inicial e rodar um fine-tuning piloto no NeMo, "
                "medindo o ganho sobre o modelo base."
            ),
        ),
    ),
    # P2 — Workflow Depth: profundidade de produto via orquestração agente/RAG com citações.
    AIMIPillar.WORKFLOW_DEPTH: (
        TechRule(
            kb_tech="NVIDIA NeMo",
            tech="NeMo Retriever (RAG)",
            prioridade=Priority.MEDIA,
            complexidade=Complexity.MEDIA,
            justificativa_tecnica=(
                "RAG com NeMo Retriever (embedding + reranking) ancora as respostas em fontes "
                "citáveis, sustentando workflows multi-passo confiáveis em vez de chamada única."
            ),
            justificativa_negocio=(
                "Aprofunda o produto (P2): mais etapas do trabalho do cliente automatizadas com "
                "rastreabilidade — autopiloto, não copiloto."
            ),
            proxima_acao=(
                "Indexar a base de conhecimento do domínio no NeMo Retriever e expor um fluxo "
                "agente com respostas citadas."
            ),
        ),
    ),
    # P4 — Distribution & Moat: governança e implantação enterprise destravam a distribuição.
    AIMIPillar.DISTRIBUTION_MOAT: (
        TechRule(
            kb_tech="NeMo Guardrails",
            tech="NeMo Guardrails",
            prioridade=Priority.ALTA,
            complexidade=Complexity.BAIXA,
            justificativa_tecnica=(
                "Rails de segurança/escopo no NeMo Guardrails contêm alucinação e uso indevido, "
                "requisito de confiabilidade para vender a clientes regulados."
            ),
            justificativa_negocio=(
                "Governança é porta de entrada enterprise (P4): destrava contas grandes que exigem "
                "controle e auditabilidade."
            ),
            proxima_acao=(
                "Definir os rails de tópico/segurança do produto no NeMo Guardrails e validar "
                "contra prompts adversariais."
            ),
        ),
        TechRule(
            kb_tech="NVIDIA NeMo",
            tech="NeMo Evaluator (avaliação)",
            prioridade=Priority.MEDIA,
            complexidade=Complexity.MEDIA,
            justificativa_tecnica=(
                "Avaliação contínua com NeMo Evaluator mede qualidade/regressão do modelo a cada "
                "mudança — governança além do guardrail em runtime."
            ),
            justificativa_negocio=(
                "Métricas auditáveis de qualidade sustentam SLA e a confiança que fecha contrato "
                "enterprise (P4)."
            ),
            proxima_acao=(
                "Montar um conjunto de avaliação do domínio no NeMo Evaluator e ligá-lo ao CI de "
                "releases do modelo."
            ),
        ),
        TechRule(
            kb_tech="NVIDIA AI Enterprise",
            tech="NVIDIA AI Enterprise",
            prioridade=Priority.MEDIA,
            complexidade=Complexity.MEDIA,
            justificativa_tecnica=(
                "Stack suportada (suporte, segurança, ciclo de vida) para operar a inferência em "
                "produção enterprise com SLA."
            ),
            justificativa_negocio=(
                "Reduz risco operacional na adoção por grandes contas — o selo de prontidão que a "
                "área de compras exige (P4)."
            ),
            proxima_acao=(
                "Avaliar o NVIDIA AI Enterprise para o ambiente de produção e mapear os requisitos "
                "de suporte/SLA dos clientes-alvo."
            ),
        ),
    ),
}


#: Domínio (setor/descrição) → techs NVIDIA de domínio recomendáveis (§5.5). Substring no texto
#: minúsculo do perfil; o primeiro setor que casar vence (uma startup tem um domínio primário,
#: mesma regra do `nvidia_rag._sector_query`).
SECTOR_RULES: tuple[SectorRule, ...] = (
    SectorRule(
        key="saude",
        stems=(
            "saúde", "saude", "health", "clínic", "clinic", "médic", "medic", "hospital",
            "diagnóstic", "diagnostic", "imagem médica", "radiolog", "patolog",
        ),
        techs=(
            TechRule(
                kb_tech="NVIDIA Clara",
                tech="NVIDIA Clara",
                prioridade=Priority.ALTA,
                complexidade=Complexity.ALTA,
                justificativa_tecnica=(
                    "Plataforma Clara para IA em saúde (imagem, genômica) com modelos e pipelines "
                    "prontos para o domínio clínico."
                ),
                justificativa_negocio=(
                    "Acelera a entrada em saúde com componentes validados — menos P&D de domínio, "
                    "mais foco no produto."
                ),
                proxima_acao="Avaliar os pipelines do Clara para o caso de uso clínico da startup.",
            ),
            TechRule(
                kb_tech="MONAI",
                tech="MONAI",
                prioridade=Priority.MEDIA,
                complexidade=Complexity.MEDIA,
                justificativa_tecnica=(
                    "Framework aberto MONAI para deep learning em imagem médica (treino, "
                    "rotulagem, deploy), co-liderado pela NVIDIA."
                ),
                justificativa_negocio=(
                    "Base open-source madura encurta o ciclo de modelo em imagem médica e a "
                    "conformidade do domínio."
                ),
                proxima_acao="Prototipar o modelo de imagem com o MONAI Core/Model Zoo.",
            ),
        ),
    ),
    SectorRule(
        key="voz",
        stems=(
            "voz", "fala", "áudio", "audio", "call center", "atendimento", "transcri",
            "speech", "voice", "contact center",
        ),
        techs=(
            TechRule(
                kb_tech="NVIDIA Riva",
                tech="NVIDIA Riva (ASR/TTS)",
                prioridade=Priority.ALTA,
                complexidade=Complexity.MEDIA,
                justificativa_tecnica=(
                    "Riva entrega ASR e TTS acelerados na GPU com baixa latência e suporte a "
                    "português — voz de qualidade de produção self-hosted."
                ),
                justificativa_negocio=(
                    "Internaliza a stack de voz (sem API de terceiro por minuto), com custo e "
                    "latência sob controle no atendimento."
                ),
                proxima_acao="Subir o Riva (ASR + TTS) e medir WER/latência em português na voz.",
            ),
        ),
    ),
    SectorRule(
        key="ciberseguranca",
        stems=(
            "segurança", "seguranca", "cyber", "fraude", "fraud", "ameaça", "threat",
            "security", "anomalia", "intrus",
        ),
        techs=(
            TechRule(
                kb_tech="NVIDIA Morpheus",
                tech="NVIDIA Morpheus",
                prioridade=Priority.ALTA,
                complexidade=Complexity.ALTA,
                justificativa_tecnica=(
                    "Morpheus processa telemetria em escala na GPU para detecção de "
                    "anomalia/fraude em tempo quase real."
                ),
                justificativa_negocio=(
                    "Detecção mais rápida e ampla reduz perda por fraude — valor direto ao cliente "
                    "de segurança."
                ),
                proxima_acao="Rodar um pipeline Morpheus sobre uma amostra de telemetria real.",
            ),
        ),
    ),
    SectorRule(
        key="robotica",
        stems=("robó", "robot", "indústria", "industria", "manufatura", "autonom", "logística"),
        techs=(
            TechRule(
                kb_tech="NVIDIA Isaac",
                tech="NVIDIA Isaac",
                prioridade=Priority.ALTA,
                complexidade=Complexity.ALTA,
                justificativa_tecnica=(
                    "Isaac oferece simulação, percepção e navegação para robótica — do treino em "
                    "sim ao deploy embarcado."
                ),
                justificativa_negocio=(
                    "Encurta o ciclo de desenvolvimento de robôs com simulação antes do hardware, "
                    "reduzindo custo de iteração."
                ),
                proxima_acao="Modelar a tarefa do robô no Isaac Sim e validar percepção/navegação.",
            ),
            TechRule(
                kb_tech="NVIDIA Omniverse",
                tech="NVIDIA Omniverse",
                prioridade=Priority.MEDIA,
                complexidade=Complexity.ALTA,
                justificativa_tecnica=(
                    "Omniverse provê o gêmeo digital/ambiente 3D físico-realista que alimenta o "
                    "treino e a validação em simulação."
                ),
                justificativa_negocio=(
                    "Gerar dado sintético e testar em sim reduz risco e custo dos testes físicos."
                ),
                proxima_acao="Montar a cena no Omniverse para gerar dado sintético do caso.",
            ),
        ),
    ),
    SectorRule(
        key="simulacao",
        stems=(
            "simulação", "simulacao", "gêmeo digital", "gemeo digital", "digital twin",
            "render", "3d", "metaverso",
        ),
        techs=(
            TechRule(
                kb_tech="NVIDIA Omniverse",
                tech="NVIDIA Omniverse",
                prioridade=Priority.ALTA,
                complexidade=Complexity.ALTA,
                justificativa_tecnica=(
                    "Omniverse é a plataforma de simulação 3D/gêmeo digital físico-realista com "
                    "colaboração e dado sintético."
                ),
                justificativa_negocio=(
                    "Substitui protótipos físicos por iteração em sim — menos custo, mais rapidez."
                ),
                proxima_acao="Reproduzir o cenário-alvo no Omniverse e validar a fidelidade.",
            ),
        ),
    ),
    SectorRule(
        # Exclusivo da F4.1 (não há query equivalente no nvidia_rag): §5.5 dados tabulares → RAPIDS.
        key="dados_tabulares",
        stems=(
            "tabular", "tabela", "planilha", "dataframe", "analytic", "analítica", "analitica",
            "etl", "data science", "ciência de dados", "ciencia de dados", "big data",
        ),
        techs=(
            TechRule(
                kb_tech="NVIDIA RAPIDS",
                tech="NVIDIA RAPIDS",
                prioridade=Priority.ALTA,
                complexidade=Complexity.MEDIA,
                justificativa_tecnica=(
                    "RAPIDS acelera o pipeline de dados (ETL→ML) na GPU com API estilo pandas/"
                    "scikit-learn — ordens de magnitude sobre CPU em dado tabular."
                ),
                justificativa_negocio=(
                    "Processar mais dado em menos tempo barateia a operação analítica e encurta o "
                    "ciclo de insight."
                ),
                proxima_acao="Portar o gargalo do pipeline tabular para RAPIDS e medir o speedup.",
            ),
            TechRule(
                kb_tech="cuDF",
                tech="cuDF",
                prioridade=Priority.MEDIA,
                complexidade=Complexity.BAIXA,
                justificativa_tecnica=(
                    "cuDF executa o dataframe (filtros, joins, agregações) na GPU com API próxima "
                    "do pandas — migração de baixo atrito."
                ),
                justificativa_negocio=(
                    "Ganho imediato de throughput no preparo de dados com mudança mínima de código."
                ),
                proxima_acao="Trocar o pandas pelo cuDF no passo mais pesado e comparar o tempo.",
            ),
            TechRule(
                kb_tech="cuML",
                tech="cuML",
                prioridade=Priority.MEDIA,
                complexidade=Complexity.MEDIA,
                justificativa_tecnica=(
                    "cuML roda ML clássico (clustering, regressão, árvores) na GPU com API "
                    "scikit-learn — treino muito mais rápido em dado tabular."
                ),
                justificativa_negocio=(
                    "Iterar modelos mais rápido acelera a entrega de valor analítico ao cliente."
                ),
                proxima_acao="Retreinar o modelo tabular no cuML e comparar tempo/qualidade.",
            ),
        ),
    ),
)


def techs_for_pillar(pilar: AIMIPillar) -> tuple[TechRule, ...]:
    """Techs prescritas para um gap de pilar (vazio se o pilar não tem regra — defensivo)."""
    return PILLAR_RULES.get(pilar, ())


def match_sector(profile: StartupProfile | None) -> SectorRule | None:
    """Setor/domínio casado a partir de setor+descrição do perfil; `None` se nada casar."""
    if profile is None:
        return None
    parts: list[str] = []
    if profile.setor is not None:
        parts.append(str(profile.setor.value))
    if profile.descricao is not None:
        parts.append(str(profile.descricao.value))
    text = " ".join(parts).lower()
    if not text:
        return None
    for rule in SECTOR_RULES:
        if any(stem in text for stem in rule.stems):
            return rule
    return None


#: P3 "graduado" — stack de inferência própria estabelecida (RUBRICA §4, banda ≥13). Acima disso a
#: jogada NVIDIA não é graduação (já graduou) e sim a **escala enterprise**: AI Enterprise (SLA/
#: suporte de produção). Espelha a região `maduro` do plano classe×AIMI (AI-native + P3 alto).
_P3_GRADUATED_MIN = 13

#: Superfície generativa/conversacional ao usuário (copiloto/chat/gerador) — gera texto livre, logo
#: risco de comportamento que pede governança (NeMo Guardrails). Espelha a regra de rótulo §5.5/F7.7.
_CONVERSATIONAL_STEMS = (
    "chat",
    "copilot",
    "assistente",
    "conversa",
    "chatbot",
    "gerador de",
    "gera texto",
    "diálogo",
    "dialogo",
)

#: As TechRules de governança/enterprise (sob P4) reusadas pelos levers F7.7 — referenciadas do
#: PILLAR_RULES p/ não duplicar o esqueleto §5.5 (uma fonte de verdade).
_AI_ENTERPRISE_RULE = next(
    r for r in PILLAR_RULES[AIMIPillar.DISTRIBUTION_MOAT] if r.kb_tech == "NVIDIA AI Enterprise"
)
_GUARDRAILS_RULE = next(
    r for r in PILLAR_RULES[AIMIPillar.DISTRIBUTION_MOAT] if r.kb_tech == "NeMo Guardrails"
)


def _has_conversational_surface(profile: StartupProfile | None) -> bool:
    """True se setor+descrição revelam superfície generativa/conversacional ao usuário (§5.5/F7.7)."""
    if profile is None:
        return False
    parts: list[str] = []
    if profile.setor is not None:
        parts.append(str(profile.setor.value))
    if profile.descricao is not None:
        parts.append(str(profile.descricao.value))
    text = " ".join(parts).lower()
    return any(stem in text for stem in _CONVERSATIONAL_STEMS)


def match_techs(
    aimi: AIMIScore, profile: StartupProfile | None = None
) -> tuple[TechCandidate, ...]:
    """Aplica as regras ao diagnóstico → techs candidatas, deduplicadas e na ordem de prescrição.

    Os gaps (mesma seleção do RAG, `gap_pillars`/F3.7) vêm primeiro, por severidade — cada um traz
    suas techs (`PILLAR_RULES`); o setor (`SECTOR_RULES`) acrescenta a tech de domínio (§5.5). Uma
    tech que aparece por mais de um gatilho é mantida **uma vez**, na primeira ocorrência (o gap
    mais severo vira o `pilar_origem`), acumulando os demais gatilhos em `triggers`. Determinístico.
    """
    # (kb_tech, tech) → posição em `order`, p/ dedup preservando a ordem de inserção.
    index: dict[tuple[str, str], int] = {}
    order: list[tuple[TechRule, AIMIPillar | None, list[str]]] = []

    def _add(rule: TechRule, pilar: AIMIPillar | None, trigger: str) -> None:
        key = (rule.kb_tech, rule.tech)
        pos = index.get(key)
        if pos is None:
            index[key] = len(order)
            order.append((rule, pilar, [trigger]))
        elif trigger not in order[pos][2]:
            order[pos][2].append(trigger)

    # Gate de prioridade (DSS §5 / ALINHAMENTO): a **graduação de infra** (pilares NVIDIA) só vale
    # p/ quem tem **core de IA provado** — um AI-native com moat. Não se prescreve a:
    #   • um *periférico* (`AI-enabled`): a IA não é o núcleo do produto (baixa prioridade);
    #   • um *wrapper frágil* (`AI-native` com P1 Data Moat **e** P2 Workflow Depth ausentes,
    #     ≤ `MAX_SCORE_WITHOUT_EVIDENCE`): "potencial ainda não comprovado" — prove o core antes.
    # A tech de **setor** (domínio declarado) segue valendo p/ ambos (AI-enabled recebe setor por
    # design, F4.8). Não afeta `alvo`/`maduro` (P1/P2 altos) nem os 7 casos §5.5 (P1=P2=20).
    unproven_wrapper = (
        aimi.data_moat.score <= MAX_SCORE_WITHOUT_EVIDENCE
        and aimi.workflow_depth.score <= MAX_SCORE_WITHOUT_EVIDENCE
    )
    emit_graduation = aimi.classificacao is Classification.AI_NATIVE and not unproven_wrapper
    if emit_graduation:
        for ps in gap_pillars(aimi):
            for rule in techs_for_pillar(ps.pilar):
                _add(rule, ps.pilar, ps.pilar.value)

    sector = match_sector(profile)
    if sector is not None:
        for rule in sector.techs:
            _add(rule, None, f"setor:{sector.key}")

    # Levers de maturidade/governança (F7.7) — aditivos, **depois** do gap/setor (o dedup preserva a
    # origem do gap quando há sobreposição, ex.: P4 já era gap). Cobrem o que o eval priority-aware
    # (recall@ALTA) expôs que a regra gap-driven não servia:
    #   • maduro: um AI-native que **já graduou** (P3 estabelecido ≥13) não precisa de graduação — a
    #     jogada NVIDIA é a **escala enterprise** → AI Enterprise (governança/SLA de produção). A
    #     evidência do lado-startup é o próprio P4 alto (origem DISTRIBUTION_MOAT, sempre citado >6).
    #   • periférico com chat: um AI-enabled com **superfície generativa/conversacional** precisa de
    #     **NeMo Guardrails** (governar comportamento) mesmo com a graduação suprimida pela classe —
    #     a IA não é o núcleo, mas a feature gera texto livre. Ancorado no perfil (origem de setor).
    if (
        aimi.classificacao is Classification.AI_NATIVE
        and aimi.technical_optimization.score >= _P3_GRADUATED_MIN
    ):
        _add(_AI_ENTERPRISE_RULE, AIMIPillar.DISTRIBUTION_MOAT, "maturidade")
    if aimi.classificacao is Classification.AI_ENABLED and _has_conversational_surface(profile):
        _add(_GUARDRAILS_RULE, None, "governanca:chat")

    return tuple(
        TechCandidate(rule=rule, pilar_origem=pilar, triggers=tuple(triggers))
        for rule, pilar, triggers in order
    )


def recommendable_kb_techs() -> frozenset[str]:
    """Conjunto de `kb_tech` referenciados pelas regras — base dos testes que amarram à KB."""
    techs: set[str] = set()
    for rules in PILLAR_RULES.values():
        techs.update(r.kb_tech for r in rules)
    for sector in SECTOR_RULES:
        techs.update(r.kb_tech for r in sector.techs)
    return frozenset(techs)


__all__ = [
    "TechRule",
    "SectorRule",
    "TechCandidate",
    "PILLAR_RULES",
    "SECTOR_RULES",
    "techs_for_pillar",
    "match_sector",
    "match_techs",
    "recommendable_kb_techs",
]
