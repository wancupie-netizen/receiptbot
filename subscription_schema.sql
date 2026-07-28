-- ReceiptBot Subscription Schema
-- Version: v1.2.2

create extension if not exists pgcrypto;


-- =========================================================
-- UPDATED_AT TRIGGER
-- =========================================================

create or replace function public.set_updated_at()
returns trigger
language plpgsql
as $$
begin
    new.updated_at = now();
    return new;
end;
$$;


-- =========================================================
-- SUBSCRIPTIONS
-- =========================================================

create table if not exists public.subscriptions (
    id uuid primary key default gen_random_uuid(),

    user_id bigint not null
        references public.users(id)
        on delete cascade,

    plan_code text not null default 'FREE'
        check (
            plan_code in (
                'FREE',
                'STARTER',
                'BUSINESS'
            )
        ),

    status text not null default 'ACTIVE'
        check (
            status in (
                'ACTIVE',
                'EXPIRED',
                'CANCELLED'
            )
        ),

    starts_at timestamptz not null default now(),

    expires_at timestamptz null,

    cancelled_at timestamptz null,

    payment_provider text null,

    payment_reference text null,

    price_rm numeric(10, 2) not null default 0
        check (price_rm >= 0),

    metadata jsonb not null default '{}'::jsonb,

    created_at timestamptz not null default now(),

    updated_at timestamptz not null default now(),

    constraint subscription_date_order_check
        check (
            expires_at is null
            or expires_at > starts_at
        )
);


create index if not exists
subscriptions_user_id_index
on public.subscriptions(user_id);


create index if not exists
subscriptions_plan_code_index
on public.subscriptions(plan_code);


create index if not exists
subscriptions_status_index
on public.subscriptions(status);


create index if not exists
subscriptions_expires_at_index
on public.subscriptions(expires_at);


-- Seorang pengguna hanya boleh mempunyai
-- satu langganan ACTIVE pada satu masa.

create unique index if not exists
subscriptions_one_active_per_user
on public.subscriptions(user_id)
where status = 'ACTIVE';


drop trigger if exists
subscriptions_set_updated_at
on public.subscriptions;


create trigger subscriptions_set_updated_at
before update
on public.subscriptions
for each row
execute function public.set_updated_at();


-- =========================================================
-- SUBSCRIPTION ADD-ONS
-- =========================================================

create table if not exists public.subscription_addons (
    id uuid primary key default gen_random_uuid(),

    subscription_id uuid not null
        references public.subscriptions(id)
        on delete cascade,

    addon_code text not null
        check (
            addon_code in (
                'EXTRA_100_RECEIPTS',
                'EXTRA_500_RECEIPTS',
                'EXTRA_STAFF',
                'ACCOUNTANT_REPORT',
                'IMPORT_CSV',
                'IMPORT_LEGACY_DATA',
                'BUSINESS_CATEGORY_SETUP',
                'WHITE_LABEL'
            )
        ),

    status text not null default 'ACTIVE'
        check (
            status in (
                'ACTIVE',
                'EXPIRED',
                'CANCELLED'
            )
        ),

    billing_type text not null
        check (
            billing_type in (
                'ONE_TIME',
                'MONTHLY'
            )
        ),

    quantity integer not null default 1
        check (quantity > 0),

    unit_price_rm numeric(10, 2) not null
        check (unit_price_rm >= 0),

    starts_at timestamptz not null default now(),

    expires_at timestamptz null,

    cancelled_at timestamptz null,

    payment_reference text null,

    metadata jsonb not null default '{}'::jsonb,

    created_at timestamptz not null default now(),

    updated_at timestamptz not null default now(),

    constraint addon_date_order_check
        check (
            expires_at is null
            or expires_at > starts_at
        )
);


create index if not exists
subscription_addons_subscription_id_index
on public.subscription_addons(subscription_id);


create index if not exists
subscription_addons_code_index
on public.subscription_addons(addon_code);


create index if not exists
subscription_addons_status_index
on public.subscription_addons(status);


-- Setiap add-on aktif disimpan dalam satu rekod.
-- Kuantiti digunakan jika pelanggan membeli lebih daripada satu.

create unique index if not exists
subscription_addons_one_active_code
on public.subscription_addons(
    subscription_id,
    addon_code
)
where status = 'ACTIVE';


drop trigger if exists
subscription_addons_set_updated_at
on public.subscription_addons;


create trigger subscription_addons_set_updated_at
before update
on public.subscription_addons
for each row
execute function public.set_updated_at();


-- =========================================================
-- ROW LEVEL SECURITY
-- =========================================================

alter table public.subscriptions
enable row level security;


alter table public.subscription_addons
enable row level security;


-- Tiada polisi anon atau authenticated diwujudkan buat masa ini.
-- ReceiptBot menggunakan Supabase Secret Key di backend.
-- Secret/service role boleh melepasi RLS.


-- =========================================================
-- SEED EXISTING USERS AS FREE
-- =========================================================

insert into public.subscriptions (
    user_id,
    plan_code,
    status,
    starts_at,
    expires_at,
    price_rm
)
select
    users.id,
    'FREE',
    'ACTIVE',
    coalesce(
        users.created_at,
        now()
    ),
    null,
    0
from public.users
where not exists (
    select 1
    from public.subscriptions
    where subscriptions.user_id = users.id
    and subscriptions.status = 'ACTIVE'
);