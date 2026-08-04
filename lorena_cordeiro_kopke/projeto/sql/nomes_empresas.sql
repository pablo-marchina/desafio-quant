-- Cole este SQL no editor do Supabase (SQL Editor > New query) e execute.
-- Só precisa rodar uma vez.

create table if not exists nomes_empresas (
  id         bigint generated always as identity primary key,
  startup    text        not null,
  titulo     text,
  url        text        not null unique,
  tags       text[]      default '{}',
  created_at timestamptz default now()
);
