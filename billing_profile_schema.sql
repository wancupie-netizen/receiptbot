-- ReceiptBot Billing Profile Schema
-- Version: v1.5.8

create extension if not exists pgcrypto;


-- =========================================================
-- UPDATED_AT FUNCTION
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
-- BILLING PROFILES
-- =========================================================

create table if not exists public.billing_profiles (
    id uuid primary key default gen_random_uuid(),

    user_id bigint not null unique
        references public.users(id)
        on delete cascade,

    telegram_id bigint not null unique,

    full_name text not null,

    email text not null,

    phone_number text not null,

    consent_at timestamptz not null,

    metadata jsonb not null default '{}'::jsonb,

    created_at timestamptz not null default now(),

    updated_at timestamptz not null default now(),

    constraint billing_profile_name_check
        check (
            length(trim(full_name)) >= 2
            and length(trim(full_name)) <= 150
        ),

    constraint billing_profile_email_check
        check (
            email ~* '^[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}$'
        ),

    constraint billing_profile_phone_check
        check (
            phone_number ~ '^\+[1-9][0-9]{7,14}$'
        )
);


-- =========================================================
-- INDEXES
-- =========================================================

create index if not exists
billing_profiles_user_id_index
on public.billing_profiles(user_id);


create index if not exists
billing_profiles_telegram_id_index
on public.billing_profiles(telegram_id);


create index if not exists
billing_profiles_email_index
on public.billing_profiles(lower(email));


-- =========================================================
-- UPDATED_AT TRIGGER
-- =========================================================

drop trigger if exists
billing_profiles_set_updated_at
on public.billing_profiles;


create trigger billing_profiles_set_updated_at
before update
on public.billing_profiles
for each row
execute function public.set_updated_at();


-- =========================================================
-- ROW LEVEL SECURITY
-- =========================================================

alter table public.billing_profiles
enable row level security;


-- Tiada polisi anon atau authenticated diwujudkan.
-- ReceiptBot menggunakan Supabase Secret Key di backend.


-- =========================================================
-- COMMENTS
-- =========================================================

comment on table public.billing_profiles is
'Maklumat pelanggan yang diperlukan untuk pembayaran ReceiptBot.';


comment on column public.billing_profiles.phone_number is
'Nombor telefon dalam format antarabangsa E.164.';


comment on column public.billing_profiles.consent_at is
'Masa pengguna bersetuju maklumat digunakan bagi urusan pembayaran.';