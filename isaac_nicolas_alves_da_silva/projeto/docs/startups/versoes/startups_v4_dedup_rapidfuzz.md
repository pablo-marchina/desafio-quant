# Startups V4 — Dedup por nome/domínio (rapidfuzz)

## Objetivo

Evitar criar duas `Startup` para a mesma empresa.

## O que entregou (slice inicial, 25/06/2026)

- `domain/policies.py::find_duplicate_startup()` — função pura: domínio
  normalizado (`normalize_domain()`, sem www/protocolo/path) bate exato →
  duplicata certa, sem fuzzy; sem bater (ou sem `website_url`), fallback por nome
  via `rapidfuzz.fuzz.WRatio()` com limiar `NAME_SIMILARITY_THRESHOLD = 92.0`.
- Limiar calibrado com **17 pares reais** (7 duplicatas conhecidas + 10 pares de
  empresas diferentes) antes de escrever a lógica — 92 é o menor valor que aceita
  toda variação de nome sem aceitar nenhum par de empresas diferentes testado.
- `StartupRepository.list_all()` (sem paginação; volume do case não justifica
  busca fuzzy indexada).
- `CreateStartup.execute()` consulta `list_all()` antes de criar; se acha
  duplicata, devolve a existente (transparente para quem chama).
- `requirements.txt` ganhou `rapidfuzz>=3.0,<4`.

Testes: 37 → 66 unit (+26 calibração, +3 caso de uso) + 1 integração.

## Limite

Confiança/auditoria por campo extraído continua futuro (foi parcialmente coberto
pelo StartupAIProfile da V5).

Versão atual do módulo: **Startups V4.1/V5** (ver `../visao_geral.md`).
