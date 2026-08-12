# ARGOS — W2 Protocol Byte Freeze

**Freeze:** `W2PF-v1.0`  
**Date:** 2026-08-12  
**Science reopened:** `false`

Os dois contratos W2 já revisados são congelados byte a byte sem qualquer edição do conteúdo original. O manifesto externo `registry/w2_protocol_freeze_manifest.json` é o ato autoritativo de freeze.

## Bytes congelados

- `registry/w2a_portfolio_accounting_protocol_draft.json` → Git blob SHA-1 `639f900eb876d6e46ecbeb10c1b3b3e6c3621a28`
- `registry/w2b_ias_protocol_draft.json` → Git blob SHA-1 `cb9a9638f236c6c61c97f86805de9bf666209b21`
- bundle ID SHA-256: `e7b48d08f657aea7552f2a692f19c1b941ebd678aa03d8ff28b961c0b317777b`

O bundle ID é calculado deterministicamente sobre os pares ordenados `path + NUL + git_blob_sha1 + LF`.

## Evidência pré-freeze

Source commit: `ede3b4c9b88b1c699424e0f3bcc76ddb37b404bc`.

- W2-A synthetic gate: 20/20 PASS.
- W2-B synthetic gate: 18/18 PASS.
- total: 38/38 PASS.
- real ARGOS performance lida durante validação: false.
- real IAS family scores lidos durante validação: false.
- Repository Hygiene do source commit: success.

## Autoridade após CI verde

- W2-A pode iniciar execução real apenas sob estes bytes e somente se Gate 0 reconciliar exatamente o legado.
- W2-C pode iniciar discovery performance-blind sob o firewall congelado W2-B.
- IAS real só pode ser pontuado depois da materialização W2-C e usando estes bytes.
- W3 continua não autorizado; W2 GO só pode autorizar o draft de um protocolo W3 separado.
- H2, M2, `C0_NO_TRADE`, FST-v1.0 e SF-v3.0 permanecem intocados.

## Imutabilidade

Qualquer alteração de um único byte invalida `W2PF-v1.0` para aquele contrato. Não é permitido simplesmente atualizar o hash esperado. A única rota válida é nova versão → justificativa → 38-case revalidation → novo freeze → execução.

## Validação

```bash
python scripts/w2_protocol_freeze_validate.py
```

O validator recalcula os Git blob SHAs a partir dos bytes do checkout, recalcula o bundle ID e exige a evidência sintética 38/38 sem contaminação.
