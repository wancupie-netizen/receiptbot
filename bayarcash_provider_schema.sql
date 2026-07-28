-- ReceiptBot BayarCash Provider Migration
-- Version: v1.5.11A
--
-- Menambah BAYARCASH sebagai payment provider rasmi.

begin;


-- =========================================================
-- PAYMENTS PROVIDER CHECK
-- =========================================================

alter table public.payments
drop constraint if exists payments_provider_code_check;


alter table public.payments
add constraint payments_provider_code_check
check (
    provider_code in (
        'NOT_CONFIGURED',
        'DEVELOPMENT',
        'BILLPLZ',
        'BAYARCASH'
    )
);


-- =========================================================
-- PAYMENT PROVIDER COMMENT
-- =========================================================

comment on column public.payments.provider_code is
'Payment provider: NOT_CONFIGURED, DEVELOPMENT, BILLPLZ atau BAYARCASH.';


commit;