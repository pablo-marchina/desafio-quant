# Scripts map

Os scripts preservam a execução científica e os gates do ARGOS. Scripts históricos continuam no `main` para permitir auditoria; não são “dead code” se reproduzem uma etapa congelada.

## Entrada atual

### Freeze científico/submissão

```bash
python scripts/final_submission_freeze_validate.py
```

Verifica consistência entre FST-v1.0, SF-v3.0, ART-030, claims/números finais, EPS residual, GenAI e manifesto.

### Higiene do repositório

```bash
python scripts/repository_hygiene_validate.py
```

Verifica que a documentação ativa não regressou para estados stale e que a camada final de navegação/autoridade existe.

## Pipelines científicos principais

- `art028_movement_data_feasibility.py` — materialização outcome-blind das features.
- `art028_finalize_architecture.py` — arquitetura pós-materialização ainda outcome-blind.
- `art029_freeze_exp07i_protocol.py` — protocolo confirmatório antes dos outcomes.
- `art030_exp07i_h2_execution.py` — execução confirmatória H2.
- `art030_runner.py` — runner de ART-030.

## Information completeness

Scripts `ic02_*`, `ic03_*`, `ic04_*`, `ic06_*`, `ic07_*` e `information_completeness_gate.py` preservam os contratos de dados usados antes do audit de técnicas.

## Cross-strategy audit

- `implementation_audit_pass_a.py`
- `implementation_audit_pass_b.py`
- scripts auxiliares de feature matrix/coverage/correlation quando presentes.

Essas etapas foram outcome-blind e fazem parte da evidência de governança.

## Status finalizers

Scripts `finalize_*_status.py` são migrações históricas de `STATUS.yaml` associadas a gates específicos. Não executá-los arbitrariamente após FST-v1.0: alguns representam transições de fase já concluídas.

O único estado vigente é o que está no `STATUS.yaml` atual.

## Política de execução

1. Rodar scripts na ordem científica prevista pelo artefato/protocolo.
2. Não alterar input congelado para “fazer passar”.
3. Preservar seeds, hashes e parâmetros.
4. Não usar outcomes em scripts explicitamente outcome-blind.
5. Não substituir campos canônicos IC-03 por vendor semantics rejeitadas.
6. Não executar novos experimentos para alterar SF-v3.0; a fase atual é relatório/QA.

## Dependências

Os workflows do GitHub Actions documentam o ambiente real usado em cada execução. Ao reproduzir um artefato histórico, prefira o workflow/commit correspondente em vez de assumir que o ambiente atual é idêntico.
