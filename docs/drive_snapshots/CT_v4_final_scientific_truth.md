# ARGOS — CURRENT TRUTH CT-v4.0

**FINAL SCIENTIFIC TRUTH**  
**Origem:** Google Drive  
**Drive ID:** `1MRWhaYaVkEwBVJTWTWtwziK7qQtFOtxJsvabzUV5Msw`  
**Classificação:** `AUTHORITATIVE_GOVERNANCE_SNAPSHOT`

Este snapshot traz ao GitHub o conteúdo operacional essencial de CT-v4.0 após ART-030 e a reconciliação final de evidências. O arquivo machine-readable `registry/final_scientific_truth.json` permanece a autoridade científica primária.

## 0. Precedência e freeze

- Constituição metodológica: `ART-027 FREEZE v1.0`.
- Tese congelada: `TF-v1.0`.
- Verdade científica final: `FST-v1.0`.
- Freeze de submissão: `SF-v3.0`.
- Proveniência: `SR-v3.0` + overlay final.

Para fatos pós-ART-030 e conteúdo da submissão, CT-v4.0/FST-v1.0/SF-v3.0 prevalecem sobre snapshots anteriores. Nenhum threshold, subgroup, feature, modelo, venue, horizonte ou regra econômica escolhido depois de observar ART-030 pode alterar a submissão. Somente erro factual/proveniência demonstrado ou conflito com fonte de maior autoridade autoriza correção.

## 1. Tese congelada

ARGOS é um sistema quantitativo de vigilância informacional concebido para testar se movimentos anormais observáveis em prediction markets contêm informação incremental além da informação pública e da probabilidade agregada antes de qualquer tradução para o ativo relacionado.

Cadeia científica:

`informação pública → probabilidade agregada do prediction market → movimentos anormais observáveis → teste incremental contra M2 → evento → ativo relacionado → long / short / no-trade após custos e incerteza`.

Wallets são contexto dos movimentos, não mecanismo automático de cópia. ARGOS não observa informação privada, intenção, ilegalidade ou identidade legal.

## 2. Estado final das hipóteses

- H1 — `SUPPORTED_IN_TESTED_SAMPLE`.
- H2 — `FAIL_UNDER_FROZEN_EXP07I`.
- H3 — `BLOCKED_BY_H2_FAIL_NO_RESCUE`.
- H4 — `BLOCKED_BY_H2_FAIL`.
- H5 — `BLOCKED_BY_H4`.

Champion probabilístico: `M2`.

Champion econômico: `C0_NO_TRADE`.

R3 permanece diagnóstico e não representa a tese ARGOS.

## 3. Resultado confirmatório de H2

O protocolo `EXP07I-H2-FREEZE-v1.0` foi congelado antes de abrir outcomes. Avaliação: 75 eventos em 54 clusters de data.

| Modelo | Brier | Log loss |
|---|---:|---:|
| M2_RAW | 0,13954701 | 0,4302918262 |
| M2_CAL | 0,1450265080 | 0,4540018561 |
| M_MOVE_CORE | 0,1620974987 | 0,5403842574 |

- ΔBrier M2_CAL − M_MOVE_CORE: `−0,0170709907`; IC95 `[−0,0491014452; 0,0128164627]`.
- ΔLogLoss: `−0,0863824013`; IC95 `[−0,2144785097; 0,0252069643]`.
- M2_RAW guard também negativo.
- 0/3 tercis temporais com incremento positivo de Brier.
- matrix-profile challenger não promovido.

Interpretação autorizada: a camada de movimentos testada não adicionou informação incremental demonstrável além de M2 sob o protocolo congelado. Isso não prova impossibilidade universal de qualquer variável futura, mas encerra H2 confirmatório do desafio e proíbe rescue pós-hoc.

## 4. Consequência econômica

Como H2 falhou, H4 e H5 não foram autorizadas como continuação causal. As traduções econômicas anteriores também não promoveram regra da tese. `C0_NO_TRADE` permanece champion econômico.

A abstention é decisão quantitativa: quando a camada adicional não demonstra valor incremental suficiente, o sistema preserva capital e evita converter ruído em posição.

R3 não pode ser apresentado como alpha do ARGOS porque não utiliza informação de prediction market.

## 5. Outcomes e proveniência

- target contratual ART-030 reconstruído: 117/117 eventos;
- auditoria independente oficial de EPS: 116/117;
- matches entre casos validados e resolução contratual: 116/116;
- divergências: 0;
- residual: `BLSH|2025-09-17`.

BLSH permanece fail-closed porque a evidência oficial encontrada não fornece explicitamente o non-GAAP EPS contratualmente compatível. Nenhum EPS é derivado sinteticamente.

ART-022 foi reconciliado; ART-025 teve Drive ID stale corrigido. Uma tentativa SEC automatizada que recebeu HTTP 403 antes do primeiro evento não promoveu dados parciais.

## 6. Claims permitidos

É permitido afirmar que:

- M2 teve valor preditivo versus os baselines públicos/gratuitos testados;
- M2 permanece champion probabilístico entre as especificações testadas;
- H2 falhou sob protocolo congelado;
- H3 não pode resgatar H2 e H4/H5 ficaram bloqueadas;
- C0_NO_TRADE é champion econômico no conjunto testado;
- 116/117 outcomes possuem reconstrução oficial independente;
- o projeto preservou PIT, hashes, resultados negativos e auditoria explícita;
- no-trade/abstention é parte do desenho quantitativo.

## 7. Claims proibidos

É proibido afirmar:

- detecção de insiders, informação privada, ilegalidade ou manipulação;
- que flow, wallets, concentração, participação ou microestrutura adicionam valor incremental além de M2;
- superioridade contra sell-side consensus PIT;
- alpha acionário, retorno líquido robusto, backtest final long/short validado, capacidade ou deployability da cadeia H2;
- R3 como evidência da tese;
- que earnings/EPS ou US equities são globalmente a família/classe de maior assimetria;
- sistema multi-market já operacional como verdade da submissão.

## 8. Limitações materiais

- `ANF|2026-05-27` e `BRZE|2026-05-27`: sem pre-cutoff tape/dense trajectory estruturalmente disponíveis.
- full historical L2: não retroativamente disponível nas superfícies first-party documentadas.
- BMO/AMC/exact release timing: não materializado de forma populacional.
- 569 V1 FeeModule BUY rows: `api_size` não canônico; usar gross token/collateral on-chain canônicos.
- contextual data recuperável mas não materializada: barrada de claims empíricos.
- sem série sell-side PIT aprovada sob R$0.
- BLSH é residual único do EPS oficial independente.

## 9. GenAI

Ledger final: 11 entradas.

GenAI foi usado em estruturação de pesquisa, triagem de fontes, código/debugging, auditoria de contratos/proveniência, desenho label-free, formalização de protocolo, execução e reconciliação crítica.

Regras:

- GenAI não conta como evidência empírica sem execução/fonte verificada;
- architecture audit e ART-029 permaneceram outcome-blind;
- outcomes foram abertos apenas após protocol hash;
- FAIL_H2 não podia ser resgatado com post-hoc features/thresholds/subgroups/models.

## 10. Freeze de submissão SF-v3.0

As sete respostas finais são:

1. Nome do Robô;
2. Explicação do Nome;
3. Lógica da Estratégia;
4. Classe de Ativos;
5. Universo de Investimento;
6. Frequência da Estratégia;
7. Benchmark.

A lógica final descreve um sistema com abstention explícita. Como H2 falhou, nenhuma execução long/short é promovida e o resultado econômico final do conjunto testado é no-trade.

## 11. Contrato do relatório final

- PDF horizontal 16:9;
- pt-BR;
- anônimo;
- máximo 5 páginas;
- autossuficiente;
- sem URL pública do repositório.

Compressão editorial não pode inverter gates, ocultar resultados negativos, remover limitações essenciais, transformar claim proibido em implicação visual ou omitir uso verificável de GenAI.

## 12. Estado final

FST-v1.0 e SF-v3.0 estão congelados. Não existem experimentos científicos adicionais autorizados para alterar a narrativa submetida.

A fase posterior é comunicação, QA, expansão separada e demonstração — não busca retroativa de um resultado melhor.
