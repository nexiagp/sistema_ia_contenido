-- NexiaGP Content Platform: durable state, assets, jobs and access boundary.
-- The browser never talks to these tables directly. The Vercel API validates the
-- Supabase session and uses the server-only service key. RLS remains enabled as
-- defence in depth should the Data API be exposed in the future.

create schema if not exists private;
revoke all on schema private from public;

create table if not exists public.app_members (
  user_id uuid primary key references auth.users(id) on delete cascade,
  role text not null check (role in ('admin', 'editor', 'viewer')),
  active boolean not null default true,
  created_at timestamptz not null default timezone('utc', now()),
  updated_at timestamptz not null default timezone('utc', now())
);

create table if not exists public.app_state (
  id smallint primary key default 1 check (id = 1),
  version bigint not null default 1 check (version > 0),
  state jsonb not null,
  updated_at timestamptz not null default timezone('utc', now()),
  updated_by uuid references auth.users(id) on delete set null
);

create table if not exists public.content_assets (
  id text primary key,
  bucket_id text not null check (bucket_id in ('source-library', 'editorial-images', 'brand-assets')),
  object_path text not null,
  kind text not null check (kind in ('source', 'image_raw', 'image_branded', 'brand', 'legacy')),
  mime_type text,
  size_bytes bigint check (size_bytes is null or size_bytes >= 0),
  sha256 text,
  legacy_url text,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default timezone('utc', now()),
  updated_at timestamptz not null default timezone('utc', now()),
  unique (bucket_id, object_path)
);

create table if not exists public.generation_jobs (
  id text primary key,
  kind text not null check (kind in ('editorial', 'blog', 'image_post', 'image_blog', 'scheduler', 'sync')),
  status text not null check (status in ('queued', 'running', 'completed', 'failed', 'cancelled')),
  request jsonb not null default '{}'::jsonb,
  progress jsonb not null default '{}'::jsonb,
  result jsonb,
  error jsonb,
  attempts integer not null default 0 check (attempts >= 0),
  locked_until timestamptz,
  requested_by uuid references auth.users(id) on delete set null,
  created_at timestamptz not null default timezone('utc', now()),
  started_at timestamptz,
  completed_at timestamptz,
  updated_at timestamptz not null default timezone('utc', now())
);

create index if not exists generation_jobs_dispatch_idx
  on public.generation_jobs (status, created_at)
  where status in ('queued', 'running');

create table if not exists public.scheduler_runs (
  id uuid primary key default gen_random_uuid(),
  run_key text not null unique,
  status text not null check (status in ('running', 'completed', 'failed')),
  started_at timestamptz not null default timezone('utc', now()),
  completed_at timestamptz,
  details jsonb not null default '{}'::jsonb
);

create table if not exists public.migration_runs (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  status text not null check (status in ('started', 'completed', 'failed')),
  manifest jsonb not null default '{}'::jsonb,
  details jsonb not null default '{}'::jsonb,
  started_at timestamptz not null default timezone('utc', now()),
  completed_at timestamptz
);

alter table public.app_members enable row level security;
alter table public.app_state enable row level security;
alter table public.content_assets enable row level security;
alter table public.generation_jobs enable row level security;
alter table public.scheduler_runs enable row level security;
alter table public.migration_runs enable row level security;

-- Explicitly remove automatic Data API privileges. API access is server-only.
revoke all on all tables in schema public from anon, authenticated;
revoke all on all sequences in schema public from anon, authenticated;

create or replace function private.touch_updated_at()
returns trigger
language plpgsql
set search_path = pg_catalog
as $$
begin
  new.updated_at = timezone('utc', now());
  return new;
end;
$$;

create or replace trigger app_members_touch_updated_at
before update on public.app_members
for each row execute function private.touch_updated_at();

create or replace trigger content_assets_touch_updated_at
before update on public.content_assets
for each row execute function private.touch_updated_at();

create or replace trigger generation_jobs_touch_updated_at
before update on public.generation_jobs
for each row execute function private.touch_updated_at();

-- Compare-and-swap keeps JSON state atomic across Vercel instances. The API
-- retries on serialization conflicts, retaining the existing server contract.
create or replace function public.replace_app_state(
  p_state jsonb,
  p_expected_version bigint,
  p_updated_by uuid default null
)
returns table (version bigint, updated_at timestamptz)
language plpgsql
security definer
set search_path = public, pg_temp
as $$
#variable_conflict use_column
begin
  update public.app_state as target
  set state = p_state,
      version = target.version + 1,
      updated_at = timezone('utc', now()),
      updated_by = p_updated_by
  where target.id = 1 and target.version = p_expected_version;

  if not found then
    raise exception 'app_state version conflict' using errcode = '40001';
  end if;

  return query
  select s.version, s.updated_at
  from public.app_state s
  where s.id = 1;
end;
$$;

create or replace function public.claim_generation_job(
  p_lease_seconds integer default 780
)
returns setof public.generation_jobs
language plpgsql
security definer
set search_path = public, pg_temp
as $$
declare
  claimed_id text;
begin
  select id into claimed_id
  from public.generation_jobs
  where status = 'queued'
     or (status = 'running' and locked_until < timezone('utc', now()))
  order by created_at
  for update skip locked
  limit 1;

  if claimed_id is null then
    return;
  end if;

  update public.generation_jobs
  set status = 'running',
      attempts = attempts + 1,
      started_at = coalesce(started_at, timezone('utc', now())),
      locked_until = timezone('utc', now()) + make_interval(secs => greatest(p_lease_seconds, 60))
  where id = claimed_id;

  return query select * from public.generation_jobs where id = claimed_id;
end;
$$;

revoke all on function public.replace_app_state(jsonb, bigint, uuid) from public, anon, authenticated;
revoke all on function public.claim_generation_job(integer) from public, anon, authenticated;
grant execute on function public.replace_app_state(jsonb, bigint, uuid) to service_role;
grant execute on function public.claim_generation_job(integer) to service_role;

insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values
  ('source-library', 'source-library', false, 52428800, array['text/plain', 'text/markdown', 'application/pdf', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', 'text/csv', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet']),
  ('editorial-images', 'editorial-images', false, 26214400, array['image/png', 'image/jpeg', 'image/webp']),
  ('brand-assets', 'brand-assets', false, 10485760, array['image/png', 'image/svg+xml'])
on conflict (id) do update
set public = excluded.public,
    file_size_limit = excluded.file_size_limit,
    allowed_mime_types = excluded.allowed_mime_types;
