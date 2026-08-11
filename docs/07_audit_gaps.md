# Auditoria de gaps e inconsistências

## BLOCKER-01 — ART-022 inconsistente

Há divergência material entre SR-v3.0 e a planilha ART-022 atual.

| Candidato | SR-v3.0 Brier | ART-022 atual Brier |
|---|---:|---:|
| T−10 | 0.198839 | 0.19937149 |
| T−5 | 0.181715 | 0.17114300 |
| T−3 | 0.164346 | 0.16884718 |
| T−1 | 0.161021 | 0.16770252 |
| ADAPT | 0.165314 | 0.17041945 |

Além disso:

- SR-v3.0 protocol hash: `c20ed9a4e16725829855ce7b2cc600fa95b818468bd09e30e55a46bd63901437`
- planilha atual protocol hash: `675f0a230b83cdda79d70f3a8d38908258e8132b30ada68b0549fb5b0d3c0006`

**Ação:** localizar os dois pacotes/protocolos, verificar timestamps, input hashes e scripts, determinar a execução autoritativa, corrigir SR/CT/HM se necessário e marcar a versão superada. Até lá, EXP-05 é proibido como número final.

## BLOCKER-02 — referência ART-025 stale

SR-v3.0 registra/referenciou em um ponto o Sheets ID `1igagDzeSOOpL3hKV9bKvzAOIvFNZM6NM35cq7nzQJ8E`, que não resolve. O arquivo atual localizado é:

`ARGOS — ART-025 Resultados EXP-06R`  
ID: `16-SejsFJeyk6GJXHCimXAWRGCUqeiEB68qsp3ZpfbsA`

**Ação:** corrigir registro mestre e qualquer manifesto dependente; validar hash/versão da planilha correta.

## BLOCKER-03 — H2 ainda não executada

O coração da tese congelada — ganho incremental de movimentos sobre M2 — ainda não tem teste populacional. Sem ART-030, H4/H5 permanecem bloqueadas.

## GAP-04 — outcomes oficiais incompletos

51/117 foram reconstruídos independentemente; 66 permanecem pendentes. Isso não invalida labels contratuais, mas limita o claim de auditoria independente.

**Decisão a tomar:** concluir os 66 ou justificar formalmente por que a subamostra auditada é suficiente para o uso no relatório, sem escrever “117 outcomes oficiais auditados”.

## GAP-05 — GenAI ledger precisa de sincronização final

ART-011 é obrigatório, mas o PDF deverá mostrar exemplos concretos e distinguir IA de decisão humana. Fechar modelos/ferramentas, etapas, entregáveis e verificações usadas.

## GAP-06 — materiais educacionais não auditados integralmente

- `Material Aula3.zip` (~173 MB): PENDING de auditoria integral.
- `Desafio Quant AI - Gravações.pdf`: índice sem transcrição textual útil; conteúdo audiovisual não auditado individualmente.

Se esses materiais não sustentarem claims, registrar explicitamente `NOT USED AS EVIDENCE` e não gastar caminho crítico.

## GAP-07 — backtest final inexistente hoje

Resultados econômicos existentes são negativos ou diagnósticos. Um backtest final coerente com ARGOS só existe se H2→H4→H5 autorizarem. Não transformar EXP-06/06R ou R3 em “backtest final” por pressão de prazo.

## GAP-08 — anonimato operacional

O repositório identifica autores. O PDF final não pode conter URL deste repo, nome da universidade, nomes pessoais, logos, metadata, comentários ou speaker notes identificáveis.
