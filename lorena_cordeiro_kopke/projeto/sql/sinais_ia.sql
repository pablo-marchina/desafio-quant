create table if not exists sinais_ia (
    id           bigint generated always as identity primary key,
    empresa_id   bigint references empresas(id) not null,
    camada       text not null check (camada in ('institucional','imprensa','gupy_vagas','neofeed')),
    encontrado   boolean not null default false,
    evidencia    text,
    fonte_url    text,
    publicado_em timestamptz,  -- preenchido apenas pela camada 'imprensa' (publishedAt da News API)
    checado_em   timestamptz default now()
  );

-- se a tabela já existir, adiciona a coluna sem recriar
alter table sinais_ia add column if not exists publicado_em timestamptz;