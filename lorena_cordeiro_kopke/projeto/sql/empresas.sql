-- Tabela de empresas (uma linha por empresa, não por notícia)
create table if not exists empresas (
  id              bigserial primary key,
  nome            text not null unique,
  dominio         text,
  gupy_subdominio text,
  created_at      timestamptz default now(),
  revisao_manual  boolean not null default false
);