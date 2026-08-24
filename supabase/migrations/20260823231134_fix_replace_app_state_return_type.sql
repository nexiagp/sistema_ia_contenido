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

revoke all on function public.replace_app_state(jsonb, bigint, uuid) from public, anon, authenticated;
grant execute on function public.replace_app_state(jsonb, bigint, uuid) to service_role;
