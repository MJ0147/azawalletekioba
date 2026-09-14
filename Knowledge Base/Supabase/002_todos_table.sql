-- Demo `todos` table backing GET /todos in the EKIOBA frontend.
-- Run in the Supabase SQL Editor. Safe to re-run.

create table if not exists public.todos (
    id           bigint generated always as identity primary key,
    name         text not null,
    is_complete  boolean not null default false,
    created_at   timestamptz not null default now()
);

alter table public.todos enable row level security;

-- This table is demo data, so reading it with the publishable (anon) key is
-- fine. Writes stay closed — there is deliberately no insert/update/delete
-- policy, so only the service-role key can modify rows.
drop policy if exists "todos are publicly readable" on public.todos;
create policy "todos are publicly readable"
    on public.todos for select
    to anon, authenticated
    using (true);

insert into public.todos (name, is_complete)
select * from (values
    ('Enable RLS on every EKIOBA table', true),
    ('Create the TON/IDIA pool on DeDust', false),
    ('Set FLW_SECRET_KEY as a Supabase secret', false)
) as seed(name, is_complete)
where not exists (select 1 from public.todos);
