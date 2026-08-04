# Scraper V7 - Validacao Semantica com Gemini

## 1. Objetivo

A segunda parte da V7 conecta a porta `SemanticValidator` a uma implementacao
concreta usando Gemini.

O Gemini nao substitui a validacao deterministica.

```txt
validacao deterministica
-> conteudo claramente bom: aceita sem Gemini
-> conteudo ruim: fallback ou rejeita sem Gemini
-> conteudo ambiguo: chama Gemini
```

---

## 2. Adaptador

Arquivo:

```txt
infrastructure/semantic_validators/gemini_semantic_validator.py
```

O adaptador implementa:

```txt
SemanticValidator
```

A pipeline continua dependendo somente da porta. Trocar Gemini por outro
provedor nao exige alterar dominio, politica ou pipeline.

---

## 3. API utilizada

A integracao usa a API REST oficial `generateContent` do Gemini por meio de
`httpx`.

```txt
POST /v1beta/models/{model}:generateContent
header x-goog-api-key
```

Nao foi adicionado um SDK do Google porque `httpx` ja existe no projeto e
mantem o adaptador pequeno e explicito.

---

## 4. Saida estruturada

A requisicao configura:

```txt
temperature = 0
responseMimeType = application/json
responseJsonSchema = GeminiSemanticResponse
```

O Gemini deve devolver:

```txt
startup_match_score
evidence_clarity_score
source_reliability_score
statement_specificity_score
context_completeness_score
contradiction_detected
decision
reason
```

A resposta e validada com Pydantic.

Regras:

```txt
scores entre 0 e 1
decision dentro do enum permitido
reason obrigatorio
campos extras proibidos
```

Resposta fora do contrato gera:

```txt
SemanticValidationError
```

---

## 5. Configuracao

Variaveis:

```env
GEMINI_API_KEY=
GEMINI_MODEL=gemini-2.5-flash
```

A factory somente cria `GeminiSemanticValidator` quando `GEMINI_API_KEY`
possui valor.

```txt
chave ausente
-> validacao semantica desligada
-> nenhum custo de Gemini

chave presente
-> validacao semantica disponivel para casos ambiguos
```

---

## 6. Controle de custo e seguranca

Configuracao atual:

```txt
Gemini chamado somente pelo LLMReviewPolicy
maximo de 20.000 caracteres enviados
timeout de 30 segundos
temperature = 0
nenhuma ferramenta ou navegacao permitida
somente texto, URL, titulo, score e warnings sao enviados
```

O prompt instrui o modelo a:

```txt
usar somente o texto fornecido
nao inventar informacoes
sinalizar contradicoes
avaliar evidencia sobre produto ou startup de IA
```

---

## 7. Tratamento de erros

```txt
timeout
-> SemanticValidationError

erro HTTP
-> SemanticValidationError

JSON ausente ou invalido
-> SemanticValidationError

campos fora do schema
-> SemanticValidationError
```

Esses erros sao conhecidos pelo modulo e fazem o job falhar de forma
controlada, sem aceitar conteudo ambiguo por acidente.

---

## 8. Fluxo completo

```txt
scraper coleta
-> validadores deterministas calculam scores
-> LLMReviewPolicy identifica ambiguidade
-> Gemini devolve fatores estruturados
-> SemanticConfidenceService calcula confianca
-> decision=accepted e confidence>=0.80
   -> aceita
-> demais resultados
   -> rejeita nesta versao
```

Agentes serao adicionados depois para tratar resultados incertos.

---

## 9. Testes

Os testes unitarios usam `httpx.MockTransport` e nao consomem a API real.

Cobertura:

```txt
header da API key
endpoint contendo o modelo
JSON Schema enviado
temperature zero
mapeamento de resposta valida
limite do texto enviado
rejeicao de resposta invalida
traducao de timeout
ativacao condicional pela factory
```

---

## 10. Teste real executado

Foi executada uma validacao controlada usando:

```txt
modelo = gemini-2.5-flash
conteudo = descricao especifica de uma plataforma de visao computacional
quality_score deterministico = 0.68
```

Resultado devolvido e calculado:

```txt
decision = accepted
semantic_confidence = 0.845
startup_match_score = 0.90
evidence_clarity_score = 0.90
contradiction_detected = false
```

Como a decisao foi `accepted` e a confianca superou `0.80`, a pipeline
aceitaria o conteudo.

Durante o primeiro teste real, a API respondeu `400 Bad Request` porque o
formato `responseFormat.text` nao era aceito pelo endpoint REST `v1beta`.

O contrato foi corrigido para:

```txt
responseMimeType = application/json
responseJsonSchema = GeminiSemanticResponse
```

Depois da correcao, a chamada real foi concluida com sucesso.

---

## 11. Como ativar

Preencha no `.env`:

```env
GEMINI_API_KEY=sua-chave
GEMINI_MODEL=gemini-2.5-flash
```

Depois reinicie API e worker para que as configuracoes sejam recarregadas.

---

## 12. Estado da suite

Depois da integracao e do teste real:

```txt
113 testes passando
```

---

## 13. Limitacoes conhecidas

```txt
prompt ainda vive dentro do adaptador
nao existem retries para falhas transitorias
tokens, latencia e custo ainda nao sao registrados
campos semanticos ficam em metadata e warnings
baixa confianca ainda termina em rejeicao
agentes ainda nao foram integrados
```

---

## 14. Proximos passos

```txt
registrar tokens, latencia e custo
versionar o prompt separadamente
adicionar retries para falhas transitorias
persistir campos semanticos em colunas dedicadas
encaminhar baixa confianca para agentes
```

---

## 15. Criterio de conclusao da V7

A V7 pode ser considerada concluida porque demonstra:

```txt
politica chama LLM somente para conteudo ambiguo
porta SemanticValidator preserva independencia de fornecedor
Gemini devolve resposta estruturada
Pydantic rejeita respostas fora do contrato
confianca e calculada pelo sistema
aceitacao exige decision accepted e confianca minima
factory ativa Gemini somente quando existe chave
chamada real foi executada com sucesso
suite completa permanece passando
```
