begin;

create extension if not exists pgcrypto with schema extensions;
create schema if not exists nvidia_inception;

do $$
declare
  exposed_schemas text;
begin
  if exists (select 1 from pg_roles where rolname = 'authenticator') then
    select split_part(setting, '=', 2)
      into exposed_schemas
      from unnest(
        coalesce(
          (select rolconfig from pg_roles where rolname = 'authenticator'),
          array[]::text[]
        )
      ) as setting
     where setting like 'pgrst.db_schemas=%'
     limit 1;

    exposed_schemas := coalesce(exposed_schemas, 'public, graphql_public');
    if not ('nvidia_inception' = any(
      string_to_array(replace(exposed_schemas, ' ', ''), ',')
    )) then
      exposed_schemas := exposed_schemas || ', nvidia_inception';
    end if;

    execute format(
      'alter role authenticator set pgrst.db_schemas = %L',
      exposed_schemas
    );
  end if;
end;
$$;

revoke all on schema nvidia_inception from public, anon, authenticated;
grant usage on schema nvidia_inception to service_role;

create or replace function nvidia_inception.set_updated_at()
returns trigger
language plpgsql
security invoker
set search_path = nvidia_inception, public
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

create table if not exists nvidia_inception.startups (
  id uuid primary key default gen_random_uuid(),
  external_id text,
  nome text not null check (length(trim(nome)) > 0),
  site_oficial text,
  categoria text,
  cidade text,
  estado varchar(2),
  pais text not null default 'Brasil',
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint startups_site_http check (
    site_oficial is null or site_oficial ~* '^https?://'
  )
);

alter table nvidia_inception.startups
  add column if not exists external_id text;

create unique index if not exists startups_nome_lower_uidx
  on nvidia_inception.startups (lower(nome));
create unique index if not exists startups_site_oficial_uidx
  on nvidia_inception.startups (site_oficial)
  where site_oficial is not null;
create unique index if not exists startups_external_id_uidx
  on nvidia_inception.startups (external_id)
  where external_id is not null;

create table if not exists nvidia_inception.pipeline_runs (
  id uuid primary key default gen_random_uuid(),
  startup_id uuid not null references nvidia_inception.startups(id) on delete cascade,
  status text not null default 'pending'
    check (status in ('pending', 'running', 'completed', 'partial', 'failed')),
  started_at timestamptz,
  finished_at timestamptz,
  duration_ms bigint check (duration_ms is null or duration_ms >= 0),
  current_stage text,
  trace_path text,
  errors jsonb not null default '[]'::jsonb,
  warnings jsonb not null default '[]'::jsonb,
  source_errors jsonb not null default '[]'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint pipeline_run_dates check (
    finished_at is null or started_at is null or finished_at >= started_at
  )
);

alter table nvidia_inception.pipeline_runs
  add column if not exists warnings jsonb not null default '[]'::jsonb;
alter table nvidia_inception.pipeline_runs
  add column if not exists source_errors jsonb not null default '[]'::jsonb;

create table if not exists nvidia_inception.search_queries (
  id uuid primary key default gen_random_uuid(),
  pipeline_run_id uuid not null references nvidia_inception.pipeline_runs(id) on delete cascade,
  consulta text not null check (length(trim(consulta)) > 0),
  camada smallint check (camada between 1 and 7),
  objetivo text,
  resultados_count integer not null default 0 check (resultados_count >= 0),
  created_at timestamptz not null default now(),
  unique (pipeline_run_id, consulta)
);

create table if not exists nvidia_inception.sources (
  id uuid primary key default gen_random_uuid(),
  pipeline_run_id uuid not null references nvidia_inception.pipeline_runs(id) on delete cascade,
  url text not null check (url ~* '^https?://'),
  tipo_fonte text not null default 'outro'
    check (tipo_fonte in ('oficial', 'imprensa', 'ecossistema', 'social', 'outro')),
  credibilidade double precision not null default 0.0
    check (credibilidade between 0.0 and 1.0),
  status text not null default 'acessivel'
    check (status in ('acessivel', 'quebrada', 'bloqueada')),
  created_at timestamptz not null default now(),
  unique (pipeline_run_id, url)
);

create table if not exists nvidia_inception.evidences (
  id uuid primary key default gen_random_uuid(),
  pipeline_run_id uuid not null references nvidia_inception.pipeline_runs(id) on delete cascade,
  source_id uuid not null references nvidia_inception.sources(id) on delete cascade,
  trecho text,
  score_confianca double precision not null default 0.0
    check (score_confianca between 0.0 and 1.0),
  classificacao text not null default 'baixa'
    check (classificacao in ('alta', 'media', 'baixa')),
  contem_ia boolean not null default false,
  descartada boolean not null default false,
  motivo_descarte text,
  created_at timestamptz not null default now(),
  constraint evidencia_descarte_motivo check (
    not descartada or motivo_descarte is not null
  ),
  unique (pipeline_run_id, source_id, trecho)
);

create table if not exists nvidia_inception.ai_assessments (
  id uuid primary key default gen_random_uuid(),
  pipeline_run_id uuid not null unique references nvidia_inception.pipeline_runs(id) on delete cascade,
  classificacao text not null
    check (classificacao in ('AI-native', 'AI-enabled', 'API-consumer', 'Non-AI')),
  nivel_maturidade smallint not null,
  confianca_classificacao double precision not null
    check (confianca_classificacao between 0.0 and 1.0),
  tecnologias_utilizadas jsonb not null default '{}'::jsonb,
  necessidades jsonb not null default '[]'::jsonb,
  justificativa text not null,
  evidencias_usadas jsonb not null default '[]'::jsonb,
  created_at timestamptz not null default now(),
  constraint assessment_maturity_check check (
    (classificacao = 'Non-AI' and nivel_maturidade = 0)
    or (classificacao <> 'Non-AI' and nivel_maturidade between 1 and 5)
  )
);

create table if not exists nvidia_inception.inception_fit_assessments (
  id uuid primary key default gen_random_uuid(),
  pipeline_run_id uuid not null unique references nvidia_inception.pipeline_runs(id) on delete cascade,
  eligibility_status text not null
    check (eligibility_status in ('eligible', 'ineligible', 'unknown')),
  startup_stage text not null
    check (startup_stage in ('early', 'growth', 'scale', 'unknown')),
  fit_json jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create table if not exists nvidia_inception.nvidia_recommendations (
  id uuid primary key default gen_random_uuid(),
  pipeline_run_id uuid not null unique references nvidia_inception.pipeline_runs(id) on delete cascade,
  recomendacao_json jsonb not null default '{}'::jsonb,
  fit_score double precision check (fit_score is null or fit_score between 0.0 and 1.0),
  created_at timestamptz not null default now()
);

create table if not exists nvidia_inception.recommendation_citations (
  id uuid primary key default gen_random_uuid(),
  recommendation_id uuid not null references nvidia_inception.nvidia_recommendations(id) on delete cascade,
  tecnologia text not null,
  trecho_doc text not null,
  url_doc text not null check (url_doc ~* '^https?://'),
  created_at timestamptz not null default now(),
  unique (recommendation_id, tecnologia, url_doc, trecho_doc)
);

create table if not exists nvidia_inception.recommendation_refinements (
  id uuid primary key default gen_random_uuid(),
  pipeline_run_id uuid not null unique references nvidia_inception.pipeline_runs(id) on delete cascade,
  refinement_json jsonb not null default '{}'::jsonb,
  fit_score double precision not null check (fit_score between 0.0 and 1.0),
  created_at timestamptz not null default now()
);

create table if not exists nvidia_inception.impact_estimates (
  id uuid primary key default gen_random_uuid(),
  pipeline_run_id uuid not null unique references nvidia_inception.pipeline_runs(id) on delete cascade,
  impact_json jsonb not null default '{}'::jsonb,
  aggregate_index smallint not null check (aggregate_index between 0 and 100),
  created_at timestamptz not null default now()
);

create table if not exists nvidia_inception.executive_briefings (
  id uuid primary key default gen_random_uuid(),
  pipeline_run_id uuid not null unique references nvidia_inception.pipeline_runs(id) on delete cascade,
  markdown text not null check (length(trim(markdown)) > 0),
  created_at timestamptz not null default now()
);

create table if not exists nvidia_inception.batch_runs (
  id uuid primary key default gen_random_uuid(),
  status text not null default 'pending'
    check (status in ('pending', 'running', 'completed', 'partial', 'failed', 'cancelled')),
  source_path text not null,
  total_items integer not null default 0 check (total_items >= 0),
  processed_items integer not null default 0 check (processed_items >= 0),
  succeeded_items integer not null default 0 check (succeeded_items >= 0),
  partial_items integer not null default 0 check (partial_items >= 0),
  failed_items integer not null default 0 check (failed_items >= 0),
  options jsonb not null default '{}'::jsonb,
  errors jsonb not null default '[]'::jsonb,
  worker_id text,
  heartbeat_at timestamptz,
  lease_expires_at timestamptz,
  started_at timestamptz,
  finished_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint batch_progress_check check (processed_items <= total_items),
  constraint batch_result_count_check check (
    succeeded_items + partial_items + failed_items <= processed_items
  )
);

alter table nvidia_inception.batch_runs
  add column if not exists worker_id text;
alter table nvidia_inception.batch_runs
  add column if not exists heartbeat_at timestamptz;
alter table nvidia_inception.batch_runs
  add column if not exists lease_expires_at timestamptz;

create table if not exists nvidia_inception.batch_items (
  id uuid primary key default gen_random_uuid(),
  batch_run_id uuid not null references nvidia_inception.batch_runs(id) on delete cascade,
  startup_external_id text not null,
  startup_name text not null check (length(trim(startup_name)) > 0),
  startup_payload jsonb not null default '{}'::jsonb,
  status text not null default 'pending'
    check (status in ('pending', 'running', 'completed', 'partial', 'failed', 'skipped')),
  pipeline_run_id uuid references nvidia_inception.pipeline_runs(id) on delete set null,
  attempt_count integer not null default 0 check (attempt_count >= 0),
  last_error text,
  result_summary jsonb not null default '{}'::jsonb,
  started_at timestamptz,
  finished_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (batch_run_id, startup_external_id)
);

create table if not exists nvidia_inception.batch_dead_letters (
  id uuid primary key default gen_random_uuid(),
  batch_run_id uuid not null references nvidia_inception.batch_runs(id) on delete cascade,
  batch_item_id uuid not null unique references nvidia_inception.batch_items(id) on delete cascade,
  startup_external_id text not null,
  startup_name text not null,
  startup_payload jsonb not null default '{}'::jsonb,
  attempt_count integer not null check (attempt_count >= 1),
  last_error text not null,
  failed_at timestamptz not null default now(),
  resolved_at timestamptz,
  created_at timestamptz not null default now()
);

create table if not exists nvidia_inception.web_content_cache (
  cache_key text primary key,
  url text not null check (url ~* '^https?://'),
  extractor text not null,
  options_hash text not null default '',
  response_json jsonb not null,
  expires_at timestamptz not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists nvidia_inception.external_api_usage (
  id uuid primary key default gen_random_uuid(),
  provider text not null,
  operation text not null,
  source_domain text,
  batch_run_id uuid references nvidia_inception.batch_runs(id) on delete set null,
  pipeline_run_id uuid references nvidia_inception.pipeline_runs(id) on delete set null,
  startup_name text,
  units integer not null default 1 check (units >= 0),
  estimated_cost_usd double precision not null default 0 check (estimated_cost_usd >= 0),
  cache_hit boolean not null default false,
  success boolean not null default true,
  created_at timestamptz not null default now()
);

create table if not exists nvidia_inception.revoked_auth_tokens (
  token_id text primary key,
  expires_at timestamptz not null,
  revoked_by text not null,
  reason text,
  created_at timestamptz not null default now()
);

create table if not exists nvidia_inception.api_rate_limits (
  rate_key text primary key,
  window_started_at timestamptz not null,
  request_count integer not null default 0 check (request_count >= 0),
  updated_at timestamptz not null default now()
);

alter table nvidia_inception.web_content_cache
  add column if not exists options_hash text not null default '';
alter table nvidia_inception.external_api_usage
  add column if not exists batch_run_id uuid references nvidia_inception.batch_runs(id) on delete set null;
alter table nvidia_inception.external_api_usage
  add column if not exists pipeline_run_id uuid references nvidia_inception.pipeline_runs(id) on delete set null;
alter table nvidia_inception.external_api_usage
  add column if not exists startup_name text;

create or replace function nvidia_inception.reserve_external_api_usage(
  p_provider text,
  p_operation text,
  p_url text,
  p_batch_run_id uuid,
  p_pipeline_run_id uuid,
  p_startup_name text,
  p_limit integer,
  p_estimated_cost_usd double precision
)
returns jsonb
language plpgsql
security definer
set search_path = nvidia_inception, public
as $$
declare
  used_units integer := 0;
  reservation_id uuid;
  used_after integer;
begin
  if p_batch_run_id is not null then
    perform pg_advisory_xact_lock(hashtextextended(p_provider || ':' || p_batch_run_id::text, 0));
    select coalesce(sum(units), 0)::integer
      into used_units
      from nvidia_inception.external_api_usage
     where provider = p_provider
       and batch_run_id = p_batch_run_id;
    if used_units >= p_limit then
      return jsonb_build_object(
        'allowed', false,
        'used', used_units,
        'limit', p_limit,
        'warning', true
      );
    end if;
  end if;

  insert into nvidia_inception.external_api_usage (
    provider, operation, source_domain, batch_run_id, pipeline_run_id,
    startup_name, units, estimated_cost_usd, cache_hit, success
  ) values (
    p_provider,
    p_operation,
    substring(p_url from '^https?://([^/]+)'),
    p_batch_run_id,
    p_pipeline_run_id,
    p_startup_name,
    1,
    greatest(coalesce(p_estimated_cost_usd, 0), 0),
    false,
    false
  ) returning id into reservation_id;

  used_after := used_units + 1;
  return jsonb_build_object(
    'allowed', true,
    'reservation_id', reservation_id,
    'used', used_after,
    'limit', p_limit,
    'warning', p_batch_run_id is not null and used_after >= ceiling(p_limit * 0.8)
  );
end;
$$;

revoke all on function nvidia_inception.reserve_external_api_usage(
  text, text, text, uuid, uuid, text, integer, double precision
) from public, anon, authenticated;
grant execute on function nvidia_inception.reserve_external_api_usage(
  text, text, text, uuid, uuid, text, integer, double precision
) to service_role;

create or replace function nvidia_inception.external_api_metrics()
returns table (
  provider text,
  requests bigint,
  cache_hits bigint,
  failures bigint,
  estimated_cost_usd double precision
)
language sql
stable
security definer
set search_path = nvidia_inception, public
as $$
  select
    usage.provider,
    coalesce(sum(usage.units), 0)::bigint as requests,
    count(*) filter (where usage.cache_hit)::bigint as cache_hits,
    count(*) filter (where not usage.success and usage.units > 0)::bigint as failures,
    coalesce(sum(usage.estimated_cost_usd), 0)::double precision as estimated_cost_usd
  from nvidia_inception.external_api_usage usage
  group by usage.provider;
$$;

revoke all on function nvidia_inception.external_api_metrics()
  from public, anon, authenticated;
grant execute on function nvidia_inception.external_api_metrics() to service_role;

create or replace function nvidia_inception.consume_api_rate_limit(
  p_key text,
  p_limit integer,
  p_window_seconds integer
)
returns jsonb
language plpgsql
security definer
set search_path = nvidia_inception, public
as $$
declare
  now_value timestamptz := now();
  current_count integer := 0;
  window_start timestamptz;
  retry_after integer;
begin
  if p_limit < 1 or p_window_seconds < 1 then
    raise exception 'Limite e janela devem ser positivos';
  end if;
  perform pg_advisory_xact_lock(hashtextextended('rate:' || p_key, 0));
  select request_count, window_started_at
    into current_count, window_start
    from nvidia_inception.api_rate_limits
   where rate_key = p_key;

  if window_start is null or window_start + make_interval(secs => p_window_seconds) <= now_value then
    current_count := 0;
    window_start := now_value;
  end if;
  retry_after := greatest(
    1,
    ceiling(extract(epoch from (window_start + make_interval(secs => p_window_seconds) - now_value)))::integer
  );
  if current_count >= p_limit then
    return jsonb_build_object(
      'allowed', false,
      'remaining', 0,
      'retry_after', retry_after
    );
  end if;

  current_count := current_count + 1;
  insert into nvidia_inception.api_rate_limits (
    rate_key, window_started_at, request_count, updated_at
  ) values (p_key, window_start, current_count, now_value)
  on conflict (rate_key) do update set
    window_started_at = excluded.window_started_at,
    request_count = excluded.request_count,
    updated_at = excluded.updated_at;

  return jsonb_build_object(
    'allowed', true,
    'remaining', greatest(p_limit - current_count, 0),
    'retry_after', retry_after
  );
end;
$$;

revoke all on function nvidia_inception.consume_api_rate_limit(text, integer, integer)
  from public, anon, authenticated;
grant execute on function nvidia_inception.consume_api_rate_limit(text, integer, integer)
  to service_role;

create index if not exists pipeline_runs_startup_id_idx
  on nvidia_inception.pipeline_runs(startup_id);
create index if not exists pipeline_runs_status_idx
  on nvidia_inception.pipeline_runs(status);
create index if not exists search_queries_run_id_idx
  on nvidia_inception.search_queries(pipeline_run_id);
create index if not exists sources_run_id_idx
  on nvidia_inception.sources(pipeline_run_id);
create index if not exists sources_status_idx
  on nvidia_inception.sources(status);
create index if not exists evidences_run_id_idx
  on nvidia_inception.evidences(pipeline_run_id);
create index if not exists evidences_classificacao_idx
  on nvidia_inception.evidences(classificacao);
create index if not exists assessments_run_id_idx
  on nvidia_inception.ai_assessments(pipeline_run_id);
create index if not exists assessments_classificacao_idx
  on nvidia_inception.ai_assessments(classificacao);
create index if not exists recommendations_run_id_idx
  on nvidia_inception.nvidia_recommendations(pipeline_run_id);
create index if not exists citations_recommendation_id_idx
  on nvidia_inception.recommendation_citations(recommendation_id);
create index if not exists refinements_run_id_idx
  on nvidia_inception.recommendation_refinements(pipeline_run_id);
create index if not exists impact_estimates_run_id_idx
  on nvidia_inception.impact_estimates(pipeline_run_id);
create index if not exists executive_briefings_run_id_idx
  on nvidia_inception.executive_briefings(pipeline_run_id);
create index if not exists batch_runs_status_idx
  on nvidia_inception.batch_runs(status);
create index if not exists batch_runs_heartbeat_idx
  on nvidia_inception.batch_runs(heartbeat_at)
  where status = 'running';
create index if not exists batch_items_batch_status_idx
  on nvidia_inception.batch_items(batch_run_id, status);
create index if not exists batch_items_pipeline_run_id_idx
  on nvidia_inception.batch_items(pipeline_run_id);
create index if not exists batch_dead_letters_batch_run_id_idx
  on nvidia_inception.batch_dead_letters(batch_run_id);
create index if not exists web_content_cache_expires_idx
  on nvidia_inception.web_content_cache(expires_at);
create index if not exists external_api_usage_provider_created_idx
  on nvidia_inception.external_api_usage(provider, created_at);
create index if not exists external_api_usage_batch_provider_idx
  on nvidia_inception.external_api_usage(batch_run_id, provider);

drop trigger if exists startups_set_updated_at on nvidia_inception.startups;
create trigger startups_set_updated_at
before update on nvidia_inception.startups
for each row execute function nvidia_inception.set_updated_at();

drop trigger if exists pipeline_runs_set_updated_at on nvidia_inception.pipeline_runs;
create trigger pipeline_runs_set_updated_at
before update on nvidia_inception.pipeline_runs
for each row execute function nvidia_inception.set_updated_at();

drop trigger if exists batch_runs_set_updated_at on nvidia_inception.batch_runs;
create trigger batch_runs_set_updated_at
before update on nvidia_inception.batch_runs
for each row execute function nvidia_inception.set_updated_at();

drop trigger if exists batch_items_set_updated_at on nvidia_inception.batch_items;
create trigger batch_items_set_updated_at
before update on nvidia_inception.batch_items
for each row execute function nvidia_inception.set_updated_at();

drop trigger if exists web_content_cache_set_updated_at on nvidia_inception.web_content_cache;
create trigger web_content_cache_set_updated_at
before update on nvidia_inception.web_content_cache
for each row execute function nvidia_inception.set_updated_at();

alter table nvidia_inception.startups enable row level security;
alter table nvidia_inception.pipeline_runs enable row level security;
alter table nvidia_inception.search_queries enable row level security;
alter table nvidia_inception.sources enable row level security;
alter table nvidia_inception.evidences enable row level security;
alter table nvidia_inception.ai_assessments enable row level security;
alter table nvidia_inception.inception_fit_assessments enable row level security;
alter table nvidia_inception.nvidia_recommendations enable row level security;
alter table nvidia_inception.recommendation_citations enable row level security;
alter table nvidia_inception.recommendation_refinements enable row level security;
alter table nvidia_inception.impact_estimates enable row level security;
alter table nvidia_inception.executive_briefings enable row level security;
alter table nvidia_inception.batch_runs enable row level security;
alter table nvidia_inception.batch_items enable row level security;
alter table nvidia_inception.batch_dead_letters enable row level security;
alter table nvidia_inception.web_content_cache enable row level security;
alter table nvidia_inception.external_api_usage enable row level security;
alter table nvidia_inception.revoked_auth_tokens enable row level security;
alter table nvidia_inception.api_rate_limits enable row level security;

do $$
declare
  table_name text;
begin
  foreach table_name in array array[
    'startups', 'pipeline_runs', 'search_queries', 'sources', 'evidences',
    'ai_assessments', 'inception_fit_assessments', 'nvidia_recommendations', 'recommendation_citations',
    'recommendation_refinements', 'impact_estimates', 'executive_briefings',
    'batch_runs', 'batch_items', 'batch_dead_letters', 'web_content_cache',
    'external_api_usage', 'revoked_auth_tokens', 'api_rate_limits'
  ] loop
    execute format('drop policy if exists service_role_all on nvidia_inception.%I', table_name);
    execute format(
      'create policy service_role_all on nvidia_inception.%I for all to service_role '
      'using ((select auth.role()) = ''service_role'') '
      'with check ((select auth.role()) = ''service_role'')',
      table_name
    );
  end loop;
end;
$$;

grant all on all tables in schema nvidia_inception to service_role;
grant all on all sequences in schema nvidia_inception to service_role;
grant execute on all functions in schema nvidia_inception to service_role;
alter default privileges for role postgres in schema nvidia_inception
  grant all on tables to service_role;
alter default privileges for role postgres in schema nvidia_inception
  grant all on sequences to service_role;
alter default privileges for role postgres in schema nvidia_inception
  grant execute on functions to service_role;

insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values (
  'pipeline-traces',
  'pipeline-traces',
  false,
  52428800,
  array['application/json']
)
on conflict (id) do update set
  public = excluded.public,
  file_size_limit = excluded.file_size_limit,
  allowed_mime_types = excluded.allowed_mime_types;

commit;

notify pgrst, 'reload config';
notify pgrst, 'reload schema';
