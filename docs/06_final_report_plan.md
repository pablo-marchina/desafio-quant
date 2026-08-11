# Plano de ação — relatório final e QA

**Entrega:** 17/08/2026.  
**Fase vigente:** `FINAL_REPORT_AUTHORING_AND_QA`.  
**Ciência:** congelada em `FST-v1.0 / SF-v3.0`; não abrir nova busca de resultado.

## Objetivo

Transformar a evidência já congelada em um PDF anônimo, autossuficiente, visual e rigoroso de **até 5 páginas, horizontal 16:9**, maximizando os critérios da banca sem alterar a verdade científica.

## Contrato editorial

O relatório deve mostrar simultaneamente:

- identidade ARGOS e problema econômico;
- mecanismo e modelagem;
- dados e disciplina point-in-time;
- evidência positiva de H1;
- resultado confirmatório negativo de H2;
- consequência econômica no-trade;
- resultados anteriores relevantes sem promover R3;
- uso concreto de GenAI e controles humanos;
- limitações materiais;
- conclusão crítica.

Qualquer número usado precisa existir em `registry/final_submission_numbers.csv`. Qualquer frase material precisa respeitar `registry/final_submission_claims.csv`.

## Arquitetura sugerida das cinco páginas

### Página 1 — ARGOS: tese e decisão

- nome/identidade visual;
- pergunta central;
- cadeia `public info → M2 → movimentos → teste incremental → ativo → trade/no-trade`;
- headline final: **probabilidade teve valor; movimentos não passaram o gate; sistema abstém**.

### Página 2 — dados e desenho anti-bias

- universo: 117 eventos earnings/EPS;
- trade tape + dense probability 115/117;
- auditoria EPS 116/117;
- protocolo outcome-blind;
- walk-forward, same-date batching, hashes e stop rules;
- limitações críticas sem poluir a página.

### Página 3 — resultado informacional

- evidência H1 de M2;
- tabela/gráfico H2 `M2_RAW / M2_CAL / M_MOVE_CORE`;
- ΔBrier/ΔLogLoss e 0/3 tercis;
- destacar `FAIL_H2`, não apenas “não significativo”.

### Página 4 — consequência econômica e falsificações

- H2 FAIL → H3/H4/H5 bloqueadas;
- `C0_NO_TRADE` champion econômico;
- R1 e regras anteriores falharam;
- R3 aparece, se necessário, apenas como exemplo de **resultado atraente recusado por desalinhamento causal**.

### Página 5 — GenAI, conclusão e limitações

- 2–3 usos de GenAI com maior impacto;
- outcome firewall e human-in-the-loop;
- erro/limitação encontrado com apoio de IA e como foi verificado;
- conclusão científica;
- limitações e possíveis trabalhos futuros claramente separados da evidência submetida.

## Checklist de autoria

- [ ] nenhuma URL pública do repositório no PDF;
- [ ] nenhuma identidade pessoal/institucional;
- [ ] nenhum claim proibido;
- [ ] todos os números rastreáveis ao registry final;
- [ ] H2 escrito como FAIL sob protocolo congelado;
- [ ] no-trade explicado como decisão, não como ausência de estratégia;
- [ ] R3 rotulado `diagnostic-only` se aparecer;
- [ ] BLSH mantido como residual, sem EPS sintético;
- [ ] GenAI descrita por contribuição + validação humana;
- [ ] material limitations presentes onde necessárias para interpretar números.

## Checklist técnico do PDF

- [ ] `≤ 5` páginas;
- [ ] horizontal `16:9`;
- [ ] pt-BR;
- [ ] legível em tela cheia sem zoom;
- [ ] sem speaker notes/comments/metadados identificáveis;
- [ ] sem links necessários para entender a entrega;
- [ ] texto e figuras não cortados;
- [ ] PDF reaberto e inspecionado após exportação;
- [ ] hash SHA-256 final registrado;
- [ ] nome final `[chave].pdf`;
- [ ] comprovante de submissão preservado.

## QA científico antes da exportação

Rodar:

```bash
python scripts/final_submission_freeze_validate.py
python scripts/repository_hygiene_validate.py
```

E comparar manualmente o PDF contra:

- `registry/final_scientific_truth.json`;
- `registry/final_submission_claims.csv`;
- `registry/final_submission_numbers.csv`;
- `registry/final_submission_answers_sf_v3.json`.

## Regra de mudança

Após FST-v1.0/SF-v3.0, **design pode mudar; ciência não**. Só corrigir o freeze se surgir erro factual/proveniência demonstrado ou conflito com fonte oficial mais autoritativa.
