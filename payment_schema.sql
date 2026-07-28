-- ReceiptBot Payment Schema
-- Version: v1.5.3
--
-- Tujuan:
-- 1. Menyimpan setiap percubaan pembayaran.
-- 2. Menyokong audit transaksi.
-- 3. Menyediakan asas webhook dan auto-upgrade.
-- 4. Memisahkan payment gateway daripada subscription.

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
-- PAYMENTS
-- =========================================================

create table if not exists public.payments (
    id uuid primary key default gen_random_uuid(),

    -- Rujukan dalaman ReceiptBot.
    payment_reference text not null unique,

    -- Pemilik pembayaran.
    user_id bigint not null
        references public.users(id)
        on delete cascade,

    -- Snapshot Telegram ID untuk audit dan notifikasi.
    telegram_id bigint not null,

    -- Pelan yang hendak dibeli.
    plan_code text not null
        check (
            plan_code in (
                'STARTER',
                'BUSINESS'
            )
        ),

    -- Subscription yang diwujudkan selepas pembayaran berjaya.
    -- Boleh NULL semasa pembayaran masih PENDING.
    subscription_id uuid null
        references public.subscriptions(id)
        on delete set null,

    -- Payment gateway.
    provider_code text not null
        check (
            provider_code in (
                'NOT_CONFIGURED',
                'DEVELOPMENT',
                'BILLPLZ'
            )
        ),

    -- ID transaksi daripada payment gateway.
    provider_reference text null,

    -- Harga semasa checkout dicipta.
    amount_rm numeric(10, 2) not null
        check (amount_rm > 0),

    currency_code text not null default 'MYR'
        check (currency_code = 'MYR'),

    status text not null default 'PENDING'
        check (
            status in (
                'PENDING',
                'PAID',
                'FAILED',
                'CANCELLED',
                'REFUNDED'
            )
        ),

    checkout_url text null,

    -- Maklumat pelanggan pada masa checkout.
    customer_name text not null,

    customer_email text null,

    customer_phone text null,

    description text null,

    -- Digunakan untuk mengelakkan checkout berganda
    -- apabila request yang sama dihantar semula.
    idempotency_key text null unique,

    -- Masa checkout tidak lagi sah.
    expires_at timestamptz null,

    -- Masa mengikut perubahan status.
    paid_at timestamptz null,

    failed_at timestamptz null,

    cancelled_at timestamptz null,

    refunded_at timestamptz null,

    -- Masa webhook terakhir diterima.
    webhook_received_at timestamptz null,

    -- Data tambahan ReceiptBot.
    metadata jsonb not null default '{}'::jsonb,

    -- Respons atau data mentah gateway.
    provider_payload jsonb not null default '{}'::jsonb,

    created_at timestamptz not null default now(),

    updated_at timestamptz not null default now(),


    -- Checkout tidak boleh tamat sebelum ia dicipta.
    constraint payments_expiry_order_check
        check (
            expires_at is null
            or expires_at > created_at
        ),


    -- PAID wajib mempunyai paid_at.
    constraint payments_paid_timestamp_check
        check (
            status <> 'PAID'
            or paid_at is not null
        ),


    -- FAILED wajib mempunyai failed_at.
    constraint payments_failed_timestamp_check
        check (
            status <> 'FAILED'
            or failed_at is not null
        ),


    -- CANCELLED wajib mempunyai cancelled_at.
    constraint payments_cancelled_timestamp_check
        check (
            status <> 'CANCELLED'
            or cancelled_at is not null
        ),


    -- REFUNDED wajib mempunyai paid_at dan refunded_at.
    constraint payments_refunded_timestamp_check
        check (
            status <> 'REFUNDED'
            or (
                paid_at is not null
                and refunded_at is not null
            )
        ),


    -- Subscription hanya boleh dipautkan selepas bayaran
    -- berjaya atau telah dipulangkan.
    constraint payments_subscription_status_check
        check (
            subscription_id is null
            or status in (
                'PAID',
                'REFUNDED'
            )
        )
);


-- =========================================================
-- INDEXES
-- =========================================================

create index if not exists
payments_user_id_index
on public.payments(user_id);


create index if not exists
payments_telegram_id_index
on public.payments(telegram_id);


create index if not exists
payments_status_index
on public.payments(status);


create index if not exists
payments_plan_code_index
on public.payments(plan_code);


create index if not exists
payments_provider_code_index
on public.payments(provider_code);


create index if not exists
payments_created_at_index
on public.payments(created_at desc);


create index if not exists
payments_subscription_id_index
on public.payments(subscription_id);


-- ID gateway mestilah unik dalam gateway yang sama.
create unique index if not exists
payments_provider_reference_unique
on public.payments(
    provider_code,
    provider_reference
)
where provider_reference is not null;


-- Membantu semakan pembayaran PENDING pengguna.
create index if not exists
payments_pending_user_index
on public.payments(
    user_id,
    created_at desc
)
where status = 'PENDING';


-- Membantu laporan pembayaran berjaya.
create index if not exists
payments_paid_user_index
on public.payments(
    user_id,
    paid_at desc
)
where status in (
    'PAID',
    'REFUNDED'
);


-- =========================================================
-- UPDATED_AT TRIGGER
-- =========================================================

drop trigger if exists
payments_set_updated_at
on public.payments;


create trigger payments_set_updated_at
before update
on public.payments
for each row
execute function public.set_updated_at();


-- =========================================================
-- PAYMENT STATUS HISTORY
-- =========================================================

create table if not exists public.payment_status_history (
    id uuid primary key default gen_random_uuid(),

    payment_id uuid not null
        references public.payments(id)
        on delete cascade,

    old_status text null
        check (
            old_status is null
            or old_status in (
                'PENDING',
                'PAID',
                'FAILED',
                'CANCELLED',
                'REFUNDED'
            )
        ),

    new_status text not null
        check (
            new_status in (
                'PENDING',
                'PAID',
                'FAILED',
                'CANCELLED',
                'REFUNDED'
            )
        ),

    source text not null default 'SYSTEM'
        check (
            source in (
                'SYSTEM',
                'USER',
                'WEBHOOK',
                'ADMIN',
                'DEVELOPMENT'
            )
        ),

    provider_reference text null,

    notes text null,

    metadata jsonb not null default '{}'::jsonb,

    created_at timestamptz not null default now()
);


create index if not exists
payment_status_history_payment_id_index
on public.payment_status_history(
    payment_id,
    created_at desc
);


create index if not exists
payment_status_history_new_status_index
on public.payment_status_history(new_status);


-- =========================================================
-- AUTOMATIC STATUS HISTORY TRIGGER
-- =========================================================

create or replace function
public.record_payment_status_change()
returns trigger
language plpgsql
as $$
begin
    if tg_op = 'INSERT' then
        insert into public.payment_status_history (
            payment_id,
            old_status,
            new_status,
            source,
            provider_reference,
            notes
        )
        values (
            new.id,
            null,
            new.status,
            'SYSTEM',
            new.provider_reference,
            'Payment record created'
        );

        return new;
    end if;

    if old.status is distinct from new.status then
        insert into public.payment_status_history (
            payment_id,
            old_status,
            new_status,
            source,
            provider_reference,
            notes
        )
        values (
            new.id,
            old.status,
            new.status,
            'SYSTEM',
            new.provider_reference,
            'Payment status updated'
        );
    end if;

    return new;
end;
$$;


drop trigger if exists
payments_record_status_change
on public.payments;


create trigger payments_record_status_change
after insert or update of status
on public.payments
for each row
execute function public.record_payment_status_change();


-- =========================================================
-- ROW LEVEL SECURITY
-- =========================================================

alter table public.payments
enable row level security;


alter table public.payment_status_history
enable row level security;


-- Tiada polisi anon atau authenticated diwujudkan.
-- ReceiptBot menggunakan Supabase Secret Key di backend.
-- Service role boleh melepasi RLS.


-- =========================================================
-- COMMENTS
-- =========================================================

comment on table public.payments is
'Rekod transaksi pembayaran ReceiptBot.';


comment on column public.payments.payment_reference is
'ID transaksi dalaman ReceiptBot.';


comment on column public.payments.provider_reference is
'ID transaksi yang diberikan oleh payment gateway.';


comment on column public.payments.subscription_id is
'Subscription yang diaktifkan selepas pembayaran berjaya.';


comment on column public.payments.idempotency_key is
'Kunci unik untuk mengelakkan checkout berganda.';


comment on table public.payment_status_history is
'Sejarah perubahan status bagi setiap pembayaran.';