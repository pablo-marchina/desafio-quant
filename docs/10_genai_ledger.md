# GenAI Usage Ledger — consolidação final

O desafio atribui 15% da nota ao uso de IA Generativa. A fonte machine-readable é `registry/genai_usage_ledger.csv`; o summary final é `registry/genai_usage_summary.json`.

**Status:** `PASS_GENAI_LEDGER_FINAL_EVIDENCE_SYNC`.  
**Entradas finais:** **11**.  
**Human-in-the-loop:** obrigatório.  
**Outcome firewall:** preservado até ART-030.  
**Negative-result policy:** `FAIL_H2` não pode ser resgatado por IA com seleção pós-hoc.

## Papéis concretos da GenAI

| Papel | Contribuição | Controle/verificação |
|---|---|---|
| Estruturação de pesquisa | decomposição do problema, hipóteses e waves de pesquisa | revisão humana + fontes primárias |
| Triagem de fontes | comparação de APIs, papers e alternativas de dados | custo, PIT, licença, semântica e fonte verificados |
| Código | geração/revisão de scripts, builders e validators | testes, execução real, hashes e readback |
| Debugging | investigação de falhas, inconsistências e leakage | correção reproduzida antes de promover output |
| Auditoria de dados | contratos IC02–IC07, campos canônicos e provenance | confronto com APIs/contratos/fontes oficiais |
| Arquitetura outcome-blind | organização de técnicas e features antes dos outcomes | 69 técnicas auditadas; seleção sem performance target |
| Protocolo confirmatório | formalização de ART-029, gates e stop rules | freeze por hash antes da abertura dos outcomes |
| Execução confirmatória | suporte à reprodução e checagem ART-030 | métricas derivadas por código auditável |
| Reconciliação | ART-022, ART-025, EPS e claims finais | comparação contra artefatos autoritativos |
| Documentação | CT/SR/HM/FST/SF e índices operacionais | precedência e revisão factual humana |
| Comunicação | estruturação do relatório final | conteúdo subordinado ao freeze científico |

## Exemplos de alto valor para o PDF

### 1. Rejeição de uma recomendação conveniente

A IA ajudou a mapear fontes de consenso histórico PIT. Em vez de aceitar a alternativa mais sofisticada, o projeto rejeitou dependências incompatíveis com R$ 0, temporalidade ou reproduzibilidade.

**Valor:** IA acelerou exploração; o gate humano/metodológico decidiu.

### 2. Outcome firewall

A IA apoiou a auditoria cross-strategy, ART-028 e a formalização do ART-029 **sem consultar outcomes para selecionar a arquitetura**. Outcomes só foram abertos após o hash do protocolo confirmatório.

**Valor:** uso de IA sem transformar model search em data snooping.

### 3. Preservação de resultado negativo

ART-030 produziu `FAIL_H2`. A IA não foi autorizada a procurar um subgrupo, threshold, wallet cohort, feature ou modelo que “salvasse” a tese.

**Valor:** GenAI usada como ferramenta de rigor, não como máquina de p-hacking.

### 4. Detecção e reconciliação de erros

Auditorias assistidas encontraram inconsistências em ART-022, referência stale em ART-025 e limitações de EPS/BLSH. A correção exigiu confronto com artefatos e fontes, sem preencher lacunas por plausibilidade.

**Valor:** IA elevou cobertura de revisão, mas a evidência final permaneceu externa e verificável.

## Política de evidência

> **Saída de GenAI nunca constitui evidência empírica por si só.**

Uma afirmação quantitativa só é promovida após execução, source verification, testes/hashes e reconciliação contra o contrato científico.

## Política pós-H2

Após `FAIL_H2`, GenAI pode:

- explicar;
- auditar;
- visualizar;
- verificar consistência;
- ajudar a redigir e comprimir a submissão.

GenAI **não pode**:

- escolher novo threshold por performance;
- procurar subgroup rescue;
- introduzir nova feature para alterar H2;
- converter R3 em tese ARGOS;
- reabrir H4/H5 sem violar stop rule.

## Uso final no relatório

A seção de GenAI deve priorizar **impacto + controle + exemplo de falha**, não uma lista de prompts ou nomes de ferramentas. O objetivo é demonstrar que IA aumentou velocidade, cobertura e auditabilidade sem substituir decisão científica humana.
