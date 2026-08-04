# Startup Classifier Agent — guia didático

> Como o NVISION rotula a maturidade de IA de cada startup, por que foi
> construído assim e o que cada decisão ensina. Documento de aprendizado:
> o foco é **expor a mecânica**, não escondê-la.

---

## 1. Onde o Classifier entra no pipeline

O Classifier é a **quinta estação** do grafo, logo depois do Extractor:

```
... → extractor → classifier → evidence_validator → (rag → ...)
```

- **Recebe** do estado: `extracted_startups` — `StructuredStartup`s com produto,
  setor, stack e, principalmente, `ai_signals`.
- **Entrega** ao estado: `classified_startups` — cada startup rotulada como
  **AI-native / AI-enabled / Non-AI**, com justificativa e confiança.

Este é o agente que produz **o diagnóstico central** do produto: o gestor do
Inception quer saber, antes de tudo, *quão de IA* é cada startup.

---

## 2. As três categorias

O critério (definido no prompt) é deliberadamente simples e operacional:

| Rótulo | Definição | Exemplo |
|---|---|---|
| **AI-native** | IA é o **núcleo** — sem ela, o produto não existe | empresa de modelos próprios de visão computacional |
| **AI-enabled** | IA é uma **feature de apoio**; o core é outro | um ERP que ganhou um assistente com LLM |
| **Non-AI** | sem evidência de uso/desenvolvimento de IA | marketplace tradicional |

A distinção AI-native vs AI-enabled é a mais sutil e a mais valiosa: separa quem
*é* uma empresa de IA de quem *usa* IA. O LLM baseia-se **sobretudo nos
`ai_signals`** que o Extractor coletou, apoiado por `description` e `tech_stack`.

---

## 3. A ferramenta: LLM com saída estruturada (de novo)

Mesmo padrão do Extractor e do Search Planner — `with_structured_output` força o
modelo a devolver um schema, eliminando parsing de texto livre.

```python
class _ClassificationResult(BaseModel):   # ← o LLM decide
    label: Literal["AI-native", "AI-enabled", "Non-AI"]
    rationale: str        # justificativa citando os sinais usados
    confidence: Literal["high", "medium", "low"]
```

O nó passa o `StructuredStartup` **inteiro** (serializado em JSON) para o LLM —
assim o modelo enxerga todo o retrato (description + tech_stack + ai_signals),
não só os sinais isolados.

---

## 4. A decisão de schema: **aninhar, não achatar**

O que fica armazenado preserva toda a cadeia anterior:

```python
class ClassifiedStartup(BaseModel):
    startup: StructuredStartup   # ← o objeto inteiro que entrou, intacto
    label: Literal[...]
    rationale: str
    confidence: Literal[...]
```

**Por quê aninhar em vez de copiar os campos?** Porque recommendation e briefing
(à frente) precisam tanto do diagnóstico quanto dos dados originais. Aninhar
evita duplicar campos e mantém **uma cadeia única**: `classified.startup.ai_signals`
e `classified.label` no mesmo objeto. Cada agente embrulha o anterior — um padrão
que se repete no Evidence Validator (que aninha o `ClassifiedStartup`).

---

## 5. `extraction_basis == "metadata"`: **pular o LLM**

Mesma filosofia do Extractor. Se a startup chegou só com metadata (sem `content`
coletado), não há texto para julgar. Em vez de perguntar ao LLM às cegas:

```python
if startup.extraction_basis == "metadata":
    resultado = _provisorio(startup, "sem conteúdo coletado; classificação provisória")
    # -> label="Non-AI", confidence="low", SEM tocar o LLM
```

**Por que `Non-AI` e não "desconhecido"?** O enum só tem três valores, e o
conservador é **não afirmar IA sem evidência**. O `confidence="low"` + a
justificativa sinalizam que é provisório — e o Evidence Validator / loop de
re-coleta podem revisitar. Honra duas regras do projeto de uma vez: "não
inventar" e "sinalizar confiança".

---

## 6. Disciplina de erro e custo

Igual ao Extractor: **uma chamada por startup**, em `try/except`, com o
`structured_llm` instanciado preguiçosamente.

```python
try:
    r = _classificar(structured_llm, startup)
    resultado = ClassifiedStartup(startup=startup, label=r.label, ...)
except Exception:
    logger.exception(...)
    resultado = _provisorio(startup, "falha na classificação; rótulo provisório")
```

- **Erro isolado por item** — uma classificação que estoura vira fallback
  `Non-AI`/`low`; as demais seguem.
- **Preguiça** — startups só-metadata nunca criam o LLM.
- **Batching** fica anotado como otimização futura.

---

## 7. `confidence` aqui vs. o Evidence Validator

Há **dois** sinais de confiança no pipeline, e eles medem coisas diferentes —
entender a distinção é parte do aprendizado:

| Agente | O que o `confidence` mede |
|---|---|
| **Classifier** (este) | força da **evidência textual** para o rótulo |
| **Evidence Validator** | qualidade/consistência da **coleta** e das fontes |

São eixos ortogonais de propósito: um rótulo pode ter evidência textual forte
(`confidence="high"` aqui) mas vir de uma coleta frágil (o Validator rebaixa).
Não há sobreposição.

---

## 8. Como testar

```bash
uv run pytest tests/test_classifier.py -v
```

Offline, com `FakeLLM` devolvendo um `_ClassificationResult` fixo
(`monkeypatch.setattr("agents.classifier.get_llm", ...)`).

| Teste | O que prova |
|---|---|
| conteúdo → rótulo | label/rationale/confidence do LLM; `startup` aninhado intacto |
| metadata → Non-AI/low | **não chama o LLM**; rótulo provisório |
| falha isolada por item | classificação que estoura vira fallback; demais seguem |
| não-mutação | o dict de entrada não é alterado |

---

## 9. Limitações conhecidas do v1 (trabalho futuro)

- **Qualidade depende do Extractor.** Se `ai_signals` está incompleto, o rótulo
  sofre. Os dois agentes evoluem juntos.
- **Sem "score de fit" com o Inception ainda.** Hoje é só o rótulo de
  maturidade; um score numérico de aderência ao programa é um diferencial
  candidato (Entregável 6).
- **AI-native vs AI-enabled é sutil.** Casos de fronteira (muita IA de apoio)
  podem oscilar; exemplos few-shot no prompt ajudariam.
- **Uma chamada por startup** — mesmo trade-off de custo do Extractor.

---

## 10. Resumo de uma frase

> O Classifier rotula cada startup em AI-native / AI-enabled / Non-AI com um LLM
> estruturado que se apoia nos `ai_signals`, aninhando o retrato que entrou para
> preservar a cadeia, pulando o LLM (e marcando provisório) quando não há texto,
> e emitindo uma confiança de *evidência textual* distinta da confiança de
> *coleta* do Evidence Validator.
