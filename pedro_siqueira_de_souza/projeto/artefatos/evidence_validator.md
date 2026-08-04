# Evidence Validator Agent — guia didático

> Como o NVISION valida a confiança de cada diagnóstico e — o conceito novo —
> faz o grafo **voltar atrás** quando a evidência é fraca. Documento de
> aprendizado: o foco é **expor a mecânica**, não escondê-la.

---

## 1. Onde o Validator entra no pipeline

O Evidence Validator é a **sexta estação** — e a que fecha o primeiro **ciclo**
do grafo:

```
... → classifier → evidence_validator ──(confiança baixa, com orçamento)──┐
                          │                                                │
                          └──(ok / sem orçamento)──> END        scraper <──┘
```

- **Recebe** do estado: `classified_startups` — startups já rotuladas.
- **Entrega** ao estado: `validated_startups` (cada uma com uma
  `validation_confidence` própria + `issues`) e `validation_attempts` (o
  contador que protege o loop).
- **Decide o caminho:** via uma função de roteamento, manda recoletar (volta pro
  `scraper`) ou encerra (`END`).

---

## 2. A decisão de filosofia: **regras, sem LLM**

Diferente do Extractor e do Classifier, o Validator **não usa LLM**. É a
aplicação direta da dica do projeto — "estruture como regras explícitas antes
de usar LLM".

Por que aqui isso é a escolha certa, não preguiça:

- **Validar consistência é trabalho de regra**, não de inferência. "Rótulo de IA
  mas zero sinais textuais" é uma condição booleana, não uma opinião.
- **Transparência total** — dá para ler exatamente por que cada confiança caiu.
- **Determinístico e barato** — sem custo de API, sem variância.
- **Testável sem `FakeLLM`** — os testes são regras puras.
- **Deixa a mecânica do ciclo cristalina** — sem ruído de LLM no meio do loop.

Um refinamento via LLM (detectar contradições sutis no texto) fica anotado como
futuro. Bom contraste didático: o pipeline mistura agentes-LLM e agentes-regra,
cada um onde faz sentido.

---

## 3. As regras de validação

A `validation_confidence` parte da confiança do Classifier e é **rebaixada** por
ressalvas. A ordem importa: ressalvas que forçam `low` têm prioridade.

| Regra | Condição | Efeito |
|---|---|---|
| 1. sem conteúdo | `extraction_basis == "metadata"` | `low` + issue "sem conteúdo coletado" |
| 2. inconsistência | label é AI-native/AI-enabled **e** `ai_signals` vazio | `low` + issue "rótulo de IA sem sinais textuais" |
| 3. caso normal | nenhuma das acima | **herda** a confiança do Classifier |

> A regra 2 é a mais instrutiva: cruza a saída de **dois agentes** (o rótulo do
> Classifier × os sinais do Extractor) e pega a contradição entre eles. É
> exatamente o tipo de checagem barata que evita um diagnóstico bonito mas vazio.

Note que **Non-AI sem sinais não é inconsistência** — é coerente. A regra só
dispara para rótulos que *afirmam* IA.

O schema, fiel ao padrão de aninhamento:

```python
class ValidatedStartup(BaseModel):
    classified: ClassifiedStartup   # toda a cadeia anterior, intacta
    validation_confidence: Literal["high", "medium", "low"]
    issues: list[str]
```

---

## 4. ⭐ A aresta condicional (o conceito novo de LangGraph)

Até aqui o grafo era uma linha reta (`add_edge`). O Validator introduz a
primeira **bifurcação decidida em runtime**: `add_conditional_edges`.

```python
builder.add_conditional_edges(
    "evidence_validator",
    route_after_validation,        # função que decide o destino
    {"scraper": "scraper", END: END},  # mapa dos destinos possíveis
)
```

A função de roteamento recebe o estado e devolve **uma string** que precisa
estar no mapa:

```python
def route_after_validation(state) -> str:
    validadas = state.get("validated_startups", [])
    tentativas = state.get("validation_attempts", 0)
    if not validadas:
        return END
    fracao_low = (nº de "low") / len(validadas)
    if fracao_low >= LOW_RATIO_LIMIAR and tentativas < MAX_ATTEMPTS:
        return "scraper"     # recoleta
    return END               # segue/encerra
```

> **Separação importante:** o **nó** (`evidence_validator_node`) calcula e
> escreve no estado; a **função de roteamento** só *lê* o estado e decide o
> caminho. Ela não muta nada — é pura. Misturar as duas coisas é um erro comum.

---

## 5. ⭐ A guarda de terminação (sem ela, loop infinito)

Um grafo com ciclo **precisa** de uma condição de parada, senão roda para sempre.
A nossa é o contador `validation_attempts`:

- o **nó** incrementa a cada passagem: `tentativa = state.get("validation_attempts", 0) + 1`;
- o **roteamento** só recoleta enquanto `tentativas < MAX_ATTEMPTS` (= 2, ou
  seja, no máximo **1 re-coleta**).

Combinado com o limiar `LOW_RATIO_LIMIAR = 0.5` (só recoleta se ≥ metade das
startups ficou em `low`), o loop é garantidamente finito.

```
1ª passagem (attempts→1): muitas low? → scraper → ... → validator
2ª passagem (attempts→2): attempts < 2? NÃO → END   (para, sempre)
```

> **Lição central de grafos com ciclo:** todo loop precisa de um *budget*
> explícito no estado. "Quando parar" é parte do design da aresta, não um
> detalhe.

---

## 6. A ressalva honesta sobre voltar pro scraper

Voltar pro `scraper` com **as mesmas fontes** recoleta o mesmo conteúdo — então
o loop, hoje, vale como **retry de coleta instável** (rede/enricher que falhou
de forma transitória), não como melhoria garantida.

Uma versão mais esperta voltaria pro **search_planner** para *ampliar* termos e
fontes — aí a re-coleta traria material novo. Mantivemos o alvo = `scraper`
porque é o que já estava documentado no grafo, e deixamos a evolução anotada. O
**valor de aprendizado** (montar e domar um ciclo condicional com guarda) é o
mesmo nos dois casos.

---

## 7. Como testar

```bash
uv run pytest tests/test_evidence_validator.py -v
```

**Sem nenhum LLM** — regras puras. Duas frentes:

**Regras de validação:**

| Teste | O que prova |
|---|---|
| consistente → herda | `confidence` do Classifier passa adiante, `issues=[]` |
| metadata → low | regra 1 dispara |
| IA sem sinais → low | regra 2 (inconsistência entre agentes) dispara |
| Non-AI sem sinais → ok | regra 2 **não** dispara para Non-AI |
| incrementa contador | `validation_attempts` sobe a cada passagem |
| não-mutação | dict de entrada intacto |

**Roteamento (a aresta):**

| Teste | O que prova |
|---|---|
| muitas low + orçamento | retorna `"scraper"` (recoleta) |
| orçamento esgotado | retorna `END` (a guarda funciona) |
| poucas low | retorna `END` |
| lista vazia | retorna `END` |

O smoke test (`tests/test_smoke.py`) exercita o ciclo no grafo real: com coleta
vazia, o roteamento manda direto pra `END` e `validation_attempts == 1`.

---

## 8. Limitações conhecidas do v1 (trabalho futuro)

- **Regras simples.** Três regras cobrem o essencial; cruzar mais sinais
  (nº de fontes, reputação do domínio, recência) é evolução natural.
- **Re-coleta não amplia.** Como discutido em §6, voltar pro `scraper` repete a
  coleta; o ganho real vem de voltar pro `search_planner` ampliando a busca.
- **Limiar e MAX fixos.** `0.5` e `2` são chutes razoáveis; calibrar com dados
  reais fica para depois.
- **Uma fonte por startup.** Hoje não há corroboração entre múltiplas fontes — o
  sinal mais forte de confiança (a mesma startup citada em vários lugares) ainda
  não existe no pipeline.

---

## 9. Resumo de uma frase

> O Evidence Validator valida a confiança de cada diagnóstico por **regras
> transparentes** (sem LLM), aninhando a cadeia anterior, e introduz o primeiro
> **ciclo** do grafo via `add_conditional_edges` — com uma **guarda de
> terminação** (`validation_attempts < MAX`) que garante que o loop sempre para.
