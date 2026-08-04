create extension if not exists pgcrypto;

create table if not exists public.startups (
    id uuid primary key default gen_random_uuid(),
    normalized_name text not null unique,
    name text not null,
    sector text,
    created_at timestamptz not null default now()
);

create table if not exists public.analysis_runs (
    id uuid primary key default gen_random_uuid(),
    startup_id uuid not null
        references public.startups(id)
        on delete cascade,

    status text not null default 'COMPLETED'
        check (status in ('COMPLETED', 'FAILED')),

    collected_at timestamptz,
    sources_successful integer not null default 0,

    classification_category text,
    ai_native_score integer,
    wrapper_risk_score integer,
    nvidia_opportunity_score integer,

    gaps jsonb not null default '[]'::jsonb,
    full_analysis jsonb not null,

    created_at timestamptz not null default now()
);

create table if not exists public.analysis_sources (
    id uuid primary key default gen_random_uuid(),
    analysis_id uuid not null
        references public.analysis_runs(id)
        on delete cascade,

    url text not null,
    title text,
    source_type text,
    tier integer,
    priority integer,
    search_query text,

    selected boolean not null default true,
    collection_status text,
    extraction_method text,
    text_characters integer,
    word_count integer,
    error text,

    created_at timestamptz not null default now(),

    unique (analysis_id, url)
);

create table if not exists public.analysis_evidences (
    id uuid primary key default gen_random_uuid(),
    analysis_id uuid not null
        references public.analysis_runs(id)
        on delete cascade,

    category text not null,
    claim text not null,
    quote text not null,
    source_url text not null,
    evidence_status text not null,
    confidence numeric(4, 3),

    created_at timestamptz not null default now()
);

create table if not exists public.nvidia_context_items (
    id uuid primary key default gen_random_uuid(),
    analysis_id uuid not null
        references public.analysis_runs(id)
        on delete cascade,

    technology_id text not null,
    technology_name text not null,
    why_retrieved jsonb not null default '[]'::jsonb,

    created_at timestamptz not null default now(),

    unique (analysis_id, technology_id)
);

create table if not exists public.nvidia_context_evidences (
    id uuid primary key default gen_random_uuid(),
    context_item_id uuid not null
        references public.nvidia_context_items(id)
        on delete cascade,

    title text,
    text text not null,
    source_url text not null,
    tags jsonb not null default '[]'::jsonb,

    lexical_score double precision,
    semantic_score double precision,
    fused_score double precision,
    rerank_score double precision,

    created_at timestamptz not null default now()
);

create table if not exists public.recommendations (
    id uuid primary key default gen_random_uuid(),
    analysis_id uuid not null
        references public.analysis_runs(id)
        on delete cascade,

    technology_id text not null,
    technology_name text not null,
    llm_model text not null,

    priority text not null
        check (priority in ('ALTA', 'MEDIA', 'BAIXA')),

    complexity text not null
        check (complexity in ('ALTA', 'MEDIA', 'BAIXA')),

    technical_reason text not null,
    business_reason text not null,
    next_action text not null,

    created_at timestamptz not null default now(),

    unique (analysis_id, technology_id)
);

create table if not exists public.recommendation_citations (
    id uuid primary key default gen_random_uuid(),
    recommendation_id uuid not null
        references public.recommendations(id)
        on delete cascade,

    evidence_id text not null,
    source_type text not null
        check (source_type in ('startup', 'nvidia')),

    source_url text not null,
    quote text not null,

    created_at timestamptz not null default now()
);

create table if not exists public.briefings (
    id uuid primary key default gen_random_uuid(),
    analysis_id uuid not null unique
        references public.analysis_runs(id)
        on delete cascade,

    markdown text not null,
    generated_at timestamptz not null,

    created_at timestamptz not null default now()
);

create index if not exists idx_analysis_runs_startup_created
    on public.analysis_runs(startup_id, created_at desc);

create index if not exists idx_analysis_sources_analysis
    on public.analysis_sources(analysis_id);

create index if not exists idx_analysis_evidences_analysis_category
    on public.analysis_evidences(analysis_id, category);

create index if not exists idx_recommendations_analysis
    on public.recommendations(analysis_id);

create index if not exists idx_briefings_analysis
    on public.briefings(analysis_id);

alter table public.startups enable row level security;
alter table public.analysis_runs enable row level security;
alter table public.analysis_sources enable row level security;
alter table public.analysis_evidences enable row level security;
alter table public.nvidia_context_items enable row level security;
alter table public.nvidia_context_evidences enable row level security;
alter table public.recommendations enable row level security;
alter table public.recommendation_citations enable row level security;
alter table public.briefings enable row level security;

revoke all on table public.startups from anon, authenticated;
revoke all on table public.analysis_runs from anon, authenticated;
revoke all on table public.analysis_sources from anon, authenticated;
revoke all on table public.analysis_evidences from anon, authenticated;
revoke all on table public.nvidia_context_items from anon, authenticated;
revoke all on table public.nvidia_context_evidences from anon, authenticated;
revoke all on table public.recommendations from anon, authenticated;
revoke all on table public.recommendation_citations from anon, authenticated;
revoke all on table public.briefings from anon, authenticated;

grant usage on schema public to service_role;

grant all privileges on all tables in schema public
to service_role;