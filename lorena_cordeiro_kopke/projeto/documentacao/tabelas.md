# Tabelas do Banco de Dados

Banco PostgreSQL hospedado no Supabase. As tabelas seguem a ordem do pipeline: coleta → filtragem → enriquecimento → recomendação.

---

## 1. `nomes_empresas`

**Papel:** ponto de entrada do pipeline. Armazena artigos de notícias brutos junto com o nome da startup extraído de cada título.

**Colunas relevantes:**

| Coluna | Tipo | Descrição |
|---|---|---|
| `id` | bigint identity PK | identificador da linha |
| `startup` | text NOT NULL | nome extraído da notícia |
| `titulo` | text | título do artigo |
| `url` | text UNIQUE NOT NULL | URL do artigo (chave de dedup) |
| `tags` | text[] | tags herdadas da coleta |

**Arquivos que escrevem:**

- [`src/interacoes_banco/upload_nomes_empresas.py`](../src/interacoes_banco/upload_nomes_empresas.py) — faz `upsert(on_conflict="url")` com o JSON gerado por `filtro.py`.

**Arquivos que leem:**

- [`src/dados_ia_startups/analisa_neofeed.py`](../src/dados_ia_startups/analisa_neofeed.py) — lê `startup, titulo, url` para classificar quais artigos mencionam IA e gravar em `sinais_ia`.

**Observação:** `upload_empresas.py` lê o mesmo JSON do disco (não do banco) para popular a tabela `empresas`, ou seja, não há leitura de `nomes_empresas` por ele.

---

## 2. `empresas`

**Papel:** catálogo central de startups. Uma linha por empresa, independente de quantos artigos ou sinais existam sobre ela.

**Colunas relevantes:**

| Coluna | Tipo | Descrição |
|---|---|---|
| `id` | bigserial PK | identificador usado como FK em todas as outras tabelas |
| `nome` | text UNIQUE NOT NULL | nome canônico da startup |
| `dominio` | text | domínio do site institucional |
| `gupy_subdominio` | text | subdomínio da página Gupy de vagas |
| `revisao_manual` | boolean DEFAULT false | `true` quando o scraping do site foi bloqueado por Cloudflare e precisa de revisão humana |

**Arquivos que escrevem:**

- [`src/interacoes_banco/upload_empresas.py`](../src/interacoes_banco/upload_empresas.py) — popula nomes únicos via `upsert(on_conflict="nome")`.
- [`src/dados_ia_startups/descobre_institucional.py`](../src/dados_ia_startups/descobre_institucional.py) — atualiza `revisao_manual=True` quando o site está protegido por Cloudflare.
- [`src/interacoes_banco/atualiza_dominio.py`](../src/interacoes_banco/atualiza_dominio.py) — permite atualizar `dominio` e `gupy_subdominio` manualmente.

**Arquivos que leem:**

- Virtualmente todos os módulos de coleta usam `empresas` para obter `id`, `nome`, `dominio` ou `gupy_subdominio` antes de gravar sinais nas tabelas dependentes.

---

## 3. `sinais_ia`

**Papel:** registra cada evidência de uso de IA coletada por camada de pesquisa. Múltiplas linhas por empresa (uma por camada verificada).

**Colunas relevantes:**

| Coluna | Tipo | Descrição |
|---|---|---|
| `id` | bigint identity PK | — |
| `empresa_id` | bigint FK → `empresas.id` | — |
| `camada` | text CHECK | `'institucional'`, `'imprensa'`, `'gupy_vagas'`, `'neofeed'` |
| `encontrado` | boolean DEFAULT false | se a evidência foi achada |
| `evidencia` | text | trecho ou título que gerou o sinal |
| `fonte_url` | text | URL de origem |
| `publicado_em` | timestamptz | preenchido apenas pela camada `imprensa` |

**Arquivos que escrevem (um por camada):**

| Camada | Arquivo |
|---|---|
| `institucional` | [`src/dados_ia_startups/descobre_institucional.py`](../src/dados_ia_startups/descobre_institucional.py) — scraping do site da empresa com Playwright |
| `imprensa` | [`src/dados_ia_startups/descobre_imprensa.py`](../src/dados_ia_startups/descobre_imprensa.py) — busca via News API / GNews / NewsData |
| `gupy_vagas` | [`src/dados_ia_startups/descobre_gupy_vagas.py`](../src/dados_ia_startups/descobre_gupy_vagas.py) — scraping de vagas abertas no Gupy |
| `neofeed` | [`src/dados_ia_startups/analisa_neofeed.py`](../src/dados_ia_startups/analisa_neofeed.py) — classifica artigos da tabela `nomes_empresas` |

**Arquivos que leem:**

- [`src/dados_ia_startups/filtro_ia.py`](../src/dados_ia_startups/filtro_ia.py) — lê todos os sinais de cada empresa, aplica pontuação por camada (teto por camada para evitar inflação) e decide o veredito. Grava resultado em `avaliacoes_ia`.

**Pontuação por camada (definida em `_TETO_CAMADA`):**

| Camada | Teto |
|---|---|
| `institucional` | 3 |
| `neofeed` | 3 |
| `gupy_vagas` | 2 |
| `imprensa` | 2 |

Threshold de aprovação: **3 pontos** (`THRESHOLD = 3` em `filtro_ia.py`).

---

## 4. `avaliacoes_ia`

**Papel:** resultado do filtro de IA. Uma linha por empresa, com veredito (aprovada/reprovada) e pontuação agregada. Apenas empresas com `veredito = true` seguem para enriquecimento em `empresas_uso_ia`.

**Colunas relevantes:**

| Coluna | Tipo | Descrição |
|---|---|---|
| `empresa_id` | integer PK + FK → `empresas.id` | 1:1 com `empresas` |
| `pontuacao` | numeric | soma dos scores por camada |
| `veredito` | boolean | `true` = usa IA extensivamente |
| `sinais_ativos` | jsonb | quais camadas contribuíram (para auditoria) |
| `avaliado_em` | timestamptz DEFAULT now() | — |

**Arquivos que escrevem:**

- [`src/dados_ia_startups/filtro_ia.py`](../src/dados_ia_startups/filtro_ia.py) — único escritor. Faz `upsert` após agregar os sinais.

**Arquivos que leem:**

- [`src/dados_startups_selecionadas/inicia_aprofundamento.py`](../src/dados_startups_selecionadas/inicia_aprofundamento.py) — ponto de entrada do enriquecimento; filtra empresas com `veredito=true`.
- `dashboard.py` — exibe veredito e pontuação no painel.

---

## 5. `empresas_uso_ia`

**Papel:** perfil completo das startups aprovadas. Populada exclusivamente para empresas com `veredito=true` em `avaliacoes_ia`. Consolida dados públicos (CNPJ/BrasilAPI), características de produto e classificação de maturidade em IA.

**Colunas relevantes (agrupadas por origem):**

| Grupo | Colunas |
|---|---|
| Identidade / BrasilAPI | `cnpj`, `cnpj_pendente`, `razao_social`, `nome_fantasia`, `situacao_rf`, `municipio`, `uf`, `cnae_principal`, `porte`, `capital_social`, `natureza_juridica` |
| Produto e mercado | `produto`, `modelo_negocio`, `mercado_alvo`, `setor` |
| Uso de IA | `uso_ia_descricao`, `ia_e_core_product`, `ia_tipo` |
| Maturidade | `ano_fundacao`, `produto_ia_lancado`, `programa_aceleracao` (text[]), `score_maturidade_ia`, `nivel_maturidade_ia` |
| Controle | `situacao_coleta`, `enriquecido_em` |

**`situacao_coleta`** controla o fluxo de revisão:

| Valor | Significado |
|---|---|
| `informação pendente` | padrão; algum campo obrigatório falta |
| `completo` | todos os campos obrigatórios preenchidos (setado automaticamente) |
| `empresa deve ser ignorada` | definido manualmente; não segue para recomendação |
| `seguir para próxima fase apesar de incompleto` | override manual; segue mesmo com dados faltando |

**Arquivos que escrevem:**

| Arquivo | O que grava |
|---|---|
| [`src/dados_startups_selecionadas/identidade/brasil_api.py`](../src/dados_startups_selecionadas/identidade/brasil_api.py) | dados do CNPJ via BrasilAPI |
| [`src/dados_startups_selecionadas/identidade/cnpj.py`](../src/dados_startups_selecionadas/identidade/cnpj.py) | CNPJ buscado/validado |
| [`src/dados_startups_selecionadas/outros/produto.py`](../src/dados_startups_selecionadas/outros/produto.py) | `produto` |
| [`src/dados_startups_selecionadas/outros/uso_ia.py`](../src/dados_startups_selecionadas/outros/uso_ia.py) | `uso_ia_descricao` |
| [`src/dados_startups_selecionadas/outros/ia_core_product.py`](../src/dados_startups_selecionadas/outros/ia_core_product.py) | `ia_e_core_product` |
| [`src/dados_startups_selecionadas/outros/ia_tipo.py`](../src/dados_startups_selecionadas/outros/ia_tipo.py) | `ia_tipo` |
| [`src/dados_startups_selecionadas/outros/modelo_negocio.py`](../src/dados_startups_selecionadas/outros/modelo_negocio.py) | `modelo_negocio`, `mercado_alvo` |
| [`src/dados_startups_selecionadas/outros/define_setor.py`](../src/dados_startups_selecionadas/outros/define_setor.py) | `setor` |
| [`src/dados_startups_selecionadas/outros/produto_ia_lancado.py`](../src/dados_startups_selecionadas/outros/produto_ia_lancado.py) | `produto_ia_lancado` |
| [`src/dados_startups_selecionadas/outros/acelerada_ia.py`](../src/dados_startups_selecionadas/outros/acelerada_ia.py) | `programa_aceleracao` (grava como array `text[]`) |
| [`src/dados_startups_selecionadas/define_maturidade.py`](../src/dados_startups_selecionadas/define_maturidade.py) | `score_maturidade_ia`, `nivel_maturidade_ia` |
| [`src/interacoes_banco/atualiza_situacao_coleta.py`](../src/interacoes_banco/atualiza_situacao_coleta.py) | `situacao_coleta` → `'completo'` quando todos os campos obrigatórios preenchidos |
| [`src/dados_startups_selecionadas/manual/atualiza_status.py`](../src/dados_startups_selecionadas/manual/atualiza_status.py) | `situacao_coleta` manualmente |
| [`src/dados_startups_selecionadas/manual/atualiza_cnpj.py`](../src/dados_startups_selecionadas/manual/atualiza_cnpj.py) | `cnpj` manualmente |

**Arquivos que leem:**

- [`src/recomendacao/inicia_recomendacao.py`](../src/recomendacao/inicia_recomendacao.py) — filtra empresas com `situacao_coleta in ('completo', 'seguir para próxima fase apesar de incompleto')` para iniciar o pipeline de recomendação.
- `dashboard.py` — exibe perfil completo, pendentes e tabela de todas as selecionadas.

---

## 6. `recomendacoes_nvidia`

**Papel:** saída do pipeline multi-agente LangGraph. Uma recomendação por empresa (unique em `empresa_id`). Armazena o que o sistema gerou a partir do perfil de `empresas_uso_ia` — separado intencionalmente: `empresas_uso_ia` guarda fatos coletados; `recomendacoes_nvidia` guarda o que o LLM produziu.

**Colunas relevantes:**

| Coluna | Tipo | Descrição |
|---|---|---|
| `id` | serial PK | — |
| `empresa_id` | integer UNIQUE NOT NULL FK → `empresas_uso_ia` | 1:1 com a empresa |
| `versao_base_conhecimento` | text | data ISO da collection Qdrant usada na geração |
| `query` | text | query semântica gerada e enviada ao Qdrant |
| `chunks_reranqueados` | jsonb | referências dos chunks recuperados (sem texto; texto fica no Qdrant) |
| `explicacao` | jsonb | por que essas tecnologias são relevantes para a startup |
| `sintese_executiva` | jsonb | resumo executivo sem jargão para CEO / account manager |
| `roadmap` | jsonb | plano de adoção 30/60/90 dias calibrado por maturidade |
| `kit_inicio` | jsonb | container NGC, tutorial e créditos Inception sugeridos |

**Arquivos que escrevem:**

- [`src/agents/extras/nodes.py`](../src/agents/extras/nodes.py) — nó final do grafo LangGraph; faz `upsert(on_conflict="empresa_id")` com todos os campos gerados pelos 4 agentes.

**Arquivos que leem:**

- [`src/recomendacao/inicia_recomendacao.py`](../src/recomendacao/inicia_recomendacao.py) — verifica se a empresa já tem `explicacao` gravada antes de rodar o pipeline novamente.
- `dashboard.py` — exibe recomendação completa (explicação, síntese, roadmap, kit) com dados do perfil mesclados via join com `empresas_uso_ia`.
