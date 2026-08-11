# Histórico resumido do projeto

Este arquivo preserva a evolução sem permitir que versões antigas substituam o freeze atual.

## 1. Ideação

A linha inicial explorava sinais de negociação informacionalmente motivada em prediction markets antes de eventos corporativos, com atenção a earnings e IPOs e possibilidade conceitual de múltiplas venues. A proposta buscava originalidade maior do que simplesmente usar a probabilidade agregada.

## 2. Empirical core

A disponibilidade e auditabilidade da probabilidade point-in-time tornaram M0×M2 o primeiro núcleo empírico robusto. O resultado mostrou M2 superior aos baselines públicos gratuitos testados, especialmente T−3/T−1.

## 3. Tentativas de baseline mais rico

O projeto auditou consenso histórico PIT, mas a rota licenciada não era compatível com o orçamento reproduzível de R$ 0. M1-ZB foi construído como baseline público gratuito mais rico, porém não melhorou M0. M3 combinando M0+M2 também não melhorou M2.

## 4. Tradução econômica

EXP-06 testou regras pré-evento e não promoveu nenhuma. EXP-06R reformulou a lógica. R1 falhou; R3 produziu resultado diagnóstico positivo após earnings, mas não usa prediction-market information.

## 5. Deriva detectada

O resultado de R3 criou risco de o projeto trocar a pergunta original por uma regra rentável mas causalmente desconectada. ART-027 foi criado exatamente para impedir essa deriva.

## 6. Reancoragem

ART-027/CT-v3.0 congelaram o ARGOS em:

`prediction market → movimento anormal → incremento sobre M2 → evento → transmissão acionária → decisão econômica`.

R3 e EXP-06S foram removidos do caminho crítico e preservados como diagnóstico/histórico.

## 7. Estado atual

A maior parte da infraestrutura de proveniência e H1 está forte, mas a tese diferencial ainda depende de H2/EXP-07I. Portanto, o projeto está cientificamente avançado, porém ainda não possui estratégia econômica final validada.
