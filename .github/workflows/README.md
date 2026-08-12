# GitHub Actions map

A maioria dos workflows representa gates científicos históricos preservados para auditoria.

## Gates operacionais atuais

- `repository_hygiene.yml` — protege o frozen bundle/FST/SF/ART-030 e navegação ativa.
- `w2_protocol_synthetic_validation.yml` — compila e executa os validators sintéticos W2-A/W2-B e exige **20/20 + 18/18 = 38/38**, além dos flags anti-contamination.

O W2 workflow é **synthetic-only** e não congela nem executa dados reais.

## Histórico

Workflows IC, Pass A/B, ART-028/029/030, closeout, final submission freeze, report build e page-set QA permanecem como prova da sequência executada. Rerun deve usar commit/protocolo apropriado; não modificar workflow histórico para acomodar resultado posterior.

## Próxima transição

Após o W2 synthetic gate verde, o próximo ato válido é criar um freeze específico dos protocol drafts. Real W2-A/W2-C só pode ocorrer depois desse freeze. Um eventual W3 exige ainda protocolo independente e prospective adequacy antes de outcomes.
