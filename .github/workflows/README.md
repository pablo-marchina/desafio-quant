# GitHub Actions map

A maioria dos workflows representa gates científicos históricos preservados para auditoria. Não modificar workflows históricos para acomodar resultado posterior.

## Gates operacionais atuais

### Base científica

- `repository_hygiene.yml` — protege frozen submission bundle, FST/SF/ART-030 e consistência de navegação.
- `w2_protocol_synthetic_validation.yml` — gate histórico W2-A/W2-B de 20/20 + 18/18 = 38/38.

### W2-B / IAS

- `w2b_ias_v1_protocol_synthetic.yml` — valida contrato/scorer IAS antes do freeze.
- `w2b_ias_v1_freeze.yml` — byte-freeze do bundle metodológico IAS.
- `w2b_ias_evidence_validate_v1.yml` — valida matriz real + source registry após o freeze de método e antes do scoring.
- `w2b_ias_real_score_v1.yml` — executou uma vez o scorer congelado sobre a evidência congelada; run `31648588879` PASS.
- `w2b_ias_smaa_result_freeze_v1.yml` — congelou e verificou o resultado SMAA; run `31648848335` PASS.

Resultado preservado: `NO_DECISIVE_HIGHEST_ASYMMETRY_LEADER`.

### W2-C / PIT-v2.1

Os workflows de discovery, semantic validation, adjudication, coleta PIT e F1–F9 preservam a lineage completa. Semantic v1 e PIT-A v1 foram invalidados e não devem ser reutilizados. O resultado autoritativo atual é `registry/w2c_pit_v2_1_family_gates.json`.

As três famílias PIT-v2.1 testadas terminaram `NO_GO_CURRENT_PROTOCOL`, com F1/F2/F3 FAIL.

### W3 gate final

O contrato, engine e synthetic suite do último gate IAS × PIT foram congelados em `W3-GATE-FREEZE-v1.0` antes da combinação real.

- manifest: `registry/w3_go_no_go_freeze_v1_0.json`;
- bundle: `c4db745a4c38a80743ec29779f638f5ebf79ff8f7f0df0a30c9ab682ae34aac2`;
- IAS input blob: `360521ba7a2973ea1685a50c55ad5636abc631ba`;
- PIT F1–F9 input blob: `1dfbc01fe7bebfc6c2a1b09037285fef8159fbaa`.

## Próxima transição

O próximo workflow válido deve fazer apenas:

1. verificar byte identity do gate W3 e dos dois inputs;
2. executar `scripts/w3_go_no_go_v1.py` exatamente como congelado;
3. persistir a saída em branch isolada;
4. promover o mesmo blob para `main`;
5. congelar e verificar o resultado;
6. rodar `repository_hygiene.yml`.

A inferência pré-execução aponta para `NO_GO_NO_W3_PROTOCOL_CANDIDATE`, mas o workflow não pode assumir nem codificar essa saída previamente.

## Regra de autoridade

Mesmo se o gate retornar GO, o máximo que ele pode autorizar é `GO_DRAFT_W3_PROTOCOL`. Um experimento W3 ainda exigiria desenho próprio, prospective adequacy e freeze antes de outcomes.

## Histórico

Workflows IC, Pass A/B, ART-028/029/030, closeout, final submission freeze, report build, page-set QA e todas as tentativas W2 permanecem como prova da sequência executada. Falhas e invalidações são parte da auditoria e não devem ser apagadas.
