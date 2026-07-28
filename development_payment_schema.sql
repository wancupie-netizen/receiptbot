-- ReceiptBot Development Payment Confirmation
-- Version: v1.5.7

create or replace function public.activate_subscription_from_payment(
    target_payment_reference text
)
returns public.subscriptions
language plpgsql
security definer
set search_path = public
as $$
declare
    payment_record public.payments%rowtype;
    existing_subscription public.subscriptions%rowtype;
    new_subscription public.subscriptions%rowtype;
    activation_time timestamptz;
begin
    activation_time := now();

    select *
    into payment_record
    from public.payments
    where payment_reference = target_payment_reference
    for update;

    if not found then
        raise exception 'PAYMENT_NOT_FOUND';
    end if;

    if payment_record.status <> 'PAID' then
        raise exception 'PAYMENT_NOT_PAID';
    end if;

    if payment_record.plan_code not in (
        'STARTER',
        'BUSINESS'
    ) then
        raise exception 'INVALID_PAYMENT_PLAN';
    end if;

    -- Idempotency:
    -- Jika pembayaran sudah dipautkan kepada subscription,
    -- pulangkan subscription yang sama.
    if payment_record.subscription_id is not null then
        select *
        into existing_subscription
        from public.subscriptions
        where id = payment_record.subscription_id;

        if found then
            return existing_subscription;
        end if;
    end if;

    -- Tamatkan subscription aktif lama.
    update public.subscriptions
    set
        status = 'EXPIRED',
        expires_at = case
            when expires_at is null
                or expires_at > activation_time
            then activation_time
            else expires_at
        end,
        updated_at = activation_time,
        metadata = coalesce(
            metadata,
            '{}'::jsonb
        ) || jsonb_build_object(
            'expired_reason',
            'plan_replaced',
            'replacement_payment_reference',
            payment_record.payment_reference
        )
    where user_id = payment_record.user_id
      and status = 'ACTIVE';

    -- Wujudkan subscription berbayar baharu.
    insert into public.subscriptions (
        user_id,
        plan_code,
        status,
        starts_at,
        expires_at,
        cancelled_at,
        payment_provider,
        payment_reference,
        price_rm,
        metadata
    )
    values (
        payment_record.user_id,
        payment_record.plan_code,
        'ACTIVE',
        activation_time,
        activation_time + interval '30 days',
        null,
        payment_record.provider_code,
        payment_record.payment_reference,
        payment_record.amount_rm,
        jsonb_build_object(
            'source',
            'payment_activation',
            'payment_id',
            payment_record.id,
            'payment_reference',
            payment_record.payment_reference
        )
    )
    returning *
    into new_subscription;

    update public.payments
    set
        subscription_id = new_subscription.id,
        updated_at = activation_time,
        metadata = coalesce(
            metadata,
            '{}'::jsonb
        ) || jsonb_build_object(
            'subscription_activated',
            true,
            'subscription_activated_at',
            activation_time,
            'subscription_id',
            new_subscription.id
        )
    where id = payment_record.id;

    return new_subscription;
end;
$$;


revoke all
on function public.activate_subscription_from_payment(text)
from public;


grant execute
on function public.activate_subscription_from_payment(text)
to service_role;


comment on function
public.activate_subscription_from_payment(text)
is
'Activate a 30-day ReceiptBot subscription from a PAID payment.';