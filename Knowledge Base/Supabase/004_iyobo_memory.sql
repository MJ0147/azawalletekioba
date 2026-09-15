-- Private storage for Iyobo, the AI assistant: conversation memory and the
-- knowledge review queue.
--
-- Run in the Supabase SQL Editor. Safe to re-run.
--
-- WHY A SEPARATE SCHEMA
-- Supabase publishes every table in the `public` schema through its REST API,
-- and a new table there has Row Level Security switched off by default. Iyobo
-- stores people's conversations and what it remembers about them, so none of it
-- may be reachable with the site's publishable key. Everything lives in the
-- `iyobo` schema instead, which the API roles cannot use at all.
--
-- The AI assistant connects with search_path=iyobo, so the tables Google ADK
-- creates for sessions, events and user/app state on first start land here too.

create schema if not exists iyobo;

-- Keep the API roles out entirely (they never had access; this makes it explicit).
revoke all on schema iyobo from public, anon, authenticated;
alter default privileges in schema iyobo revoke all on tables from public, anon, authenticated;
alter default privileges in schema iyobo revoke all on sequences from public, anon, authenticated;

-- ── Knowledge review queue ────────────────────────────────────────────────
-- When a user teaches Iyobo something (an Edo word, a correction), it is saved
-- here as a suggestion. Nothing reaches the Knowledge Base until the project
-- owner approves it.
create table if not exists iyobo.knowledge_suggestions (
    id              bigint generated always as identity primary key,
    edo             text,
    english         text,
    category        text,
    example         text,
    note            text        not null,
    source_channel  text        not null default 'web'
                    check (source_channel in ('web', 'telegram')),
    -- A one-way hash of the user id: enough to spot one person sending many
    -- suggestions, without storing who they are.
    user_ref        text,
    status          text        not null default 'pending'
                    check (status in ('pending', 'approved', 'rejected')),
    reviewer_note   text,
    reviewed_at     timestamptz,
    created_at      timestamptz not null default now(),
    updated_at      timestamptz not null default now()
);

create index if not exists knowledge_suggestions_status_idx
    on iyobo.knowledge_suggestions (status, created_at desc);

-- Reuses the helper from 001/003 if already present.
create or replace function public.set_updated_at()
returns trigger
language plpgsql
as $$
begin
    new.updated_at = now();
    return new;
end;
$$;

drop trigger if exists knowledge_suggestions_set_updated_at on iyobo.knowledge_suggestions;
create trigger knowledge_suggestions_set_updated_at
    before update on iyobo.knowledge_suggestions
    for each row execute function public.set_updated_at();

-- Defence in depth: RLS on with no policies, so even a role that somehow gains
-- schema access sees nothing. The assistant's database role owns the table and
-- is unaffected.
alter table iyobo.knowledge_suggestions enable row level security;

comment on schema iyobo is
    'Private storage for Iyobo: ADK sessions and user memory, and the knowledge review queue. Not exposed through the Supabase API.';
comment on table iyobo.knowledge_suggestions is
    'Knowledge users taught Iyobo, awaiting the project owner''s approval before it joins the Knowledge Base.';
comment on column iyobo.knowledge_suggestions.user_ref is
    'SHA-256 of the user id with a server-side salt; never the raw id.';
