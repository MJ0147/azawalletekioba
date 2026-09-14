-- Give public."EDO" the columns needed to hold Edo Language Academy vocabulary.
--
-- Run in the Supabase SQL Editor. Safe to re-run.
--
-- NOTE ON THE TABLE NAME
-- The table was created as public."EDO" — quoted and uppercase, which makes the
-- identifier case-sensitive forever. Every query must spell it exactly
-- public."EDO"; plain `edo` or `Edo` will not resolve, and PostgREST exposes it
-- at /rest/v1/EDO. That is workable but unconventional. To switch to the usual
-- lowercase style instead, run this once and use `edo_vocabulary` everywhere:
--
--     alter table public."EDO" rename to edo_vocabulary;
--
-- The statements below deliberately target "EDO" as it exists today.

alter table public."EDO"
    add column if not exists edo        text,
    add column if not exists english    text,
    add column if not exists category   text,
    add column if not exists example    text,
    add column if not exists notes      text,
    add column if not exists updated_at timestamptz not null default now();

-- One row per headword, so re-running the loader updates instead of duplicating.
create unique index if not exists edo_headword_key on public."EDO" (edo);

create index if not exists edo_category_idx on public."EDO" (category);
create index if not exists edo_english_idx  on public."EDO" (english);

-- Keep updated_at honest (reuses the helper from 001 if already present).
create or replace function public.set_updated_at()
returns trigger
language plpgsql
as $$
begin
    new.updated_at = now();
    return new;
end;
$$;

drop trigger if exists edo_set_updated_at on public."EDO";
create trigger edo_set_updated_at
    before update on public."EDO"
    for each row execute function public.set_updated_at();

-- ── Row Level Security ───────────────────────────────────────────────────
-- RLS is already enabled on this table and anonymous reads already succeed,
-- which is the correct posture for public reference data: the vocabulary is
-- meant to be read by the Academy front end, and writes stay closed so only
-- the service-role key can load or edit entries.
--
-- These statements are idempotent and simply make that intent explicit.
alter table public."EDO" enable row level security;

drop policy if exists "edo vocabulary is publicly readable" on public."EDO";
create policy "edo vocabulary is publicly readable"
    on public."EDO" for select
    to anon, authenticated
    using (true);

-- Deliberately no insert/update/delete policy: loading is done with the
-- service-role key, which bypasses RLS.

comment on table public."EDO" is
    'Edo language vocabulary for the EKIOBA Language Academy. Publicly readable; writes are service-role only.';
comment on column public."EDO".edo is
    'Edo headword, tone-marked (e.g. mòsé). Unique.';
comment on column public."EDO".category is
    'adjectival_verb | adjective | ideophone | noun | verb | particle | number | ...';
