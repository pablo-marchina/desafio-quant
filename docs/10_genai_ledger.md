# GenAI Usage Ledger — consolidação para o relatório

O desafio atribui 15% da nota ao uso de IA Generativa. Este arquivo separa **uso prático**, **output** e **controle humano**.

## Usos já realizados

| Etapa | Contribuição da GenAI | Output prático | Controle humano / validação |
|---|---|---|---|
| Ideação | geração e comparação de teses | famílias candidatas e estrutura de hipóteses | seleção pela equipe + critérios científicos |
| Pesquisa | síntese de literatura e fontes | matriz de referências e mecanismos | checagem de papers/fontes e classificação de força |
| Data sourcing | auditoria de APIs e alternativas PIT | decisões GO/NO-GO, inclusive consenso | custo, temporalidade, licença e reproduzibilidade validados |
| Protocolo | apoio na estruturação de gates, ablações e stop rules | ARTs e freezes | decisão final pré-resultado pela equipe |
| Código | geração/revisão de scripts e builders | pipelines M1-ZB, auditorias, análises | testes unitários, reprodução, hashes e execução independente |
| Debugging | busca de inconsistências/leakage | detecção de bugs e casos-limite | correções reproduzidas e outputs regenerados |
| Auditoria | cross-check de resultados/documentos | identificação de divergências e claims indevidos | conferência contra artefatos autoritativos |
| Documentação | consolidação de CT/SR/HM e narrativa | dossiês, registros e planos | precedence/freeze e revisão factual humana |
| Relatório | estrutura, síntese e visualização | outline e, futuramente, PDF | conteúdo final subordinado aos resultados congelados |

## Exemplos fortes para citar no PDF

1. IA ajudou a investigar múltiplas fontes de consenso PIT; a equipe rejeitou opções incompatíveis com R$ 0/reproduzibilidade em vez de aceitar a recomendação mais conveniente.
2. IA apoiou a construção/revisão de protocolos confirmatórios, mas thresholds/gates foram congelados antes dos resultados.
3. Auditoria assistida identificou inconsistências, bugs e deriva narrativa; resultados positivos causalmente desalinhados foram mantidos como diagnóstico, não promovidos.
4. IA apoiou código e documentação, mas evidência numérica só foi aceita após execução, hashes e validação independente.

## Pendências antes do PDF

- [ ] registrar modelos/ferramentas efetivamente usados por etapa;
- [ ] selecionar 2–3 exemplos concretos com maior valor agregado;
- [ ] documentar pelo menos um erro/limitação da IA e como foi detectado;
- [ ] ligar exemplos a artefatos/commits verificáveis;
- [ ] não transformar “uso de IA” em lista de prompts — explicar impacto no processo.
