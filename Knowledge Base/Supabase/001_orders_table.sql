-- EKIOBA — first Supabase table: IDIA checkout orders.
--
-- Run this in the Supabase SQL Editor (Dashboard -> SQL Editor -> New query).
-- It is NOT applied automatically: creating schema in your database is your
-- call, and the publishable key cannot run DDL anyway.
--
-- Why orders: the FastAPI frontend already mints an `order_id` and a
-- `EKIOBA-<id>` comment for every TON payment request, but nothing persists
-- them — the Django `Payment` model only records a row once a transaction
-- hash comes back. This table captures the intent at checkout time so an
-- abandoned or unconfirmed payment is still traceable.
--
-- Safe to re-run.

create table if not exists public.orders (
    id              uuid primary key default gen_random_uuid(),
    order_id        text not null unique,          -- the EKIOBA-<id> reference
    product_name    text not null,
    amount_ngn      numeric(14, 2) not null check (amount_ngn > 0),
    amount_idia     numeric(24, 9) not null check (amount_idia > 0),
    chain           text not null default 'ton' check (chain = 'ton'),
    sender_address  text,                           -- connected TON wallet
    jetton_wallet   text,                           -- sender's IDIA jetton wallet
    tx_hash         text,                           -- filled in once submitted
    status          text not null default 'pending'
                    check (status in ('pending', 'submitted', 'confirmed', 'failed', 'expired')),
    is_cart_checkout boolean not null default false,
    cart_items      jsonb not null default '[]'::jsonb,
    created_at      timestamptz not null default now(),
    updated_at      timestamptz not null default now()
);

create index if not exists orders_order_id_idx   on public.orders (order_id);
create index if not exists orders_status_idx     on public.orders (status);
create index if not exists orders_created_at_idx on public.orders (created_at desc);
create index if not exists orders_sender_idx     on public.orders (sender_address);

-- Keep updated_at honest.
create or replace function public.set_updated_at()
returns trigger
language plpgsql
as $$
begin
    new.updated_at = now();
    return new;
end;
$$;

drop trigger if exists orders_set_updated_at on public.orders;
create trigger orders_set_updated_at
    before update on public.orders
    for each row execute function public.set_updated_at();

-- ── Row Level Security ───────────────────────────────────────────────────
-- REQUIRED. The publishable key is public by design; without RLS anyone
-- holding it could read and rewrite every order.
--
-- Enabling RLS with no permissive policy denies all access to the
-- publishable key. That is the correct default here: orders are written and
-- read by the EKIOBA backend using the SERVICE key, which bypasses RLS.
alter table public.orders enable row level security;

-- Deliberately no policy for `anon`.
--
-- If you later let a shopper see their own order from the browser, add a
-- narrow policy rather than opening the table, e.g. once orders carry an
-- authenticated user_id:
--
--   alter table public.orders add column user_id uuid references auth.users (id);
--
--   create policy "shoppers read their own orders"
--       on public.orders for select
--       to authenticated
--       using (auth.uid() = user_id);

comment on table public.orders is
    'IDIA checkout orders captured at payment-request time by the EKIOBA frontend.';
