# Captura de referências de Drive para entrega final — ARGOS

**Data:** 2026-08-16  
**Objetivo:** recuperar fontes disponíveis no Google Drive sobre requisitos, critérios e padrões de entrega final, separando o que é diretamente aplicável ao desafio ARGOS/Itaú Quant do que é referência acadêmica geral de turma.

---

## 1. Limitação de acesso aos snapshots oficiais espelhados no manifesto

O manifesto de submissão do repositório referencia três arquivos Google Workspace:

- Current Truth CT-v4: `1MRWhaYaVkEwBVJTWTWtwziK7qQtFOtxJsvabzUV5Msw`;
- Source Registry SR-v3: `12dGCC306uEVNC62qU8nUKL_jT__WKSD1jhzBT-VHXHk`;
- Hypothesis Matrix HM-v4: `1h1JAzYdqFurIP17_69c1ZWqcKI1NzrAbChi-DGLC8io`.

Tentativas diretas de leitura via Google Drive connector retornaram `404 File not found` para os três IDs. Portanto, para a submissão ARGOS, a autoridade operacional disponível continua sendo o espelho congelado no GitHub:

- `registry/final_scientific_truth.json`;
- `registry/final_submission_manifest.json`;
- `registry/final_submission_claims.csv`;
- `registry/final_submission_numbers.csv`;
- `docs/29_final_scientific_truth_submission_freeze.md`.

**Decisão:** não depender desses links de Drive inacessíveis para a entrega; usar os registries Git congelados como fonte autoritativa.

---

## 2. Busca no Drive por materiais específicos do desafio ARGOS/Itaú

Consultas realizadas no Drive:

- `Itaú Asset Quant AI 2026 ARGOS desafio quant final submission`;
- `ARGOS Quant`;
- `Desafio Quant Itaú Asset`;
- `Itaú Asset Quant AI relatório final PDF 5 páginas 16:9`.

Resultado: não foram encontrados documentos adicionais específicos do desafio ARGOS/Itaú além do que já está espelhado no repositório.

**Decisão:** a rubrica específica do desafio deve ser tomada dos arquivos do repo, principalmente:

- `docs/01_challenge_requirements.md`;
- `docs/06_final_report_plan.md`;
- `docs/30_report_scoring_maximization_contract.md`;
- `registry/report_scoring_maximization_matrix.csv`;
- `registry/final_submission_manifest.json`.

---

## 3. Drive de turma acessível

Foi acessível a pasta:

- `2026-2A-T24_IN03`.

Ela contém subpastas:

- `UX - Prof. Heloisa Candello`;
- `Business - Prof. Marcelo Desterro`;
- `Mathematics - Prof. Henrique`;
- `Computing - Prof. Wesley`;
- `Orientation - Prof. Camila`.

Também foi acessível a planilha de atividades associada, contendo backlog de conteúdos por semana, com materiais sobre LGPD, CRISP-DM, machine learning, data governance, UX de modelos preditivos, Git/GitLab e qualidade de dados.

**Uso para ARGOS:** referência acadêmica geral, não rubrica específica do desafio. Útil para reforçar padrões de metodologia, governança de dados, LGPD, CRISP-DM, versionamento e documentação.

---

## 4. Documento `Sprints`

A busca no Drive retornou o documento `Sprints`, com critérios de avaliação de entregas de projeto de jogo/GDD. Ele não é diretamente o edital ARGOS/Itaú, mas reforça padrões acadêmicos recorrentes:

- coerência entre requisitos, tarefas e objetivo do parceiro;
- encadeamento lógico e priorização;
- qualidade textual, gramatical e ortográfica;
- uso de board Kanban e rastreabilidade de tarefas;
- publicação no repositório Git;
- software executável sem erros;
- comentários, nomes de variáveis, indentação;
- documentação objetiva conectando implementação a requisitos;
- testes documentados com pré-condições, passos e pós-condições;
- representatividade/público-alvo quando pertinente.

**Uso para ARGOS:** não deve substituir a rubrica do desafio, mas pode orientar QA acadêmico: rastreabilidade, clareza, qualidade textual, reprodutibilidade e ligação requisito→evidência.

---

## 5. Planilha de atividades

A planilha acessada contém conteúdos e referências de curso. Os mais úteis como apoio acadêmico geral são:

- LGPD e política de dados;
- CRISP-DM;
- fundamentos de machine learning e data science;
- qualidade de dados;
- data governance;
- user needs e trust em modelos preditivos;
- Git/GitLab e revisão por Merge Request.

**Uso para ARGOS:** reforçar, quando necessário, que a entrega deve mostrar disciplina de dados, governança, rastreabilidade e explicabilidade. Não usar como fonte de claims financeiros ou resultados.

---

## 6. Conclusão de captura

A captura de Drive não adicionou uma rubrica nova específica para o desafio ARGOS/Itaú. Ela confirma dois blocos:

1. **Autoridade específica da entrega:** está no repositório, nos arquivos de requisitos, manifesto, claims, números e matriz de score.
2. **Referências acadêmicas gerais:** estão no Drive de turma e reforçam padrões de documentação, governança, versionamento, qualidade textual, rastreabilidade e metodologia.

**Status:** `PASS_DRIVE_REFERENCE_CAPTURE_WITH_REPO_AS_AUTHORITATIVE_CHALLENGE_SOURCE`.
