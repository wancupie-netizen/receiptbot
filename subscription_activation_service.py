from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from database import supabase
from payment_repository import (
    PaymentRecord,
    get_payment_by_reference,
    link_payment_to_subscription,
)
from payment_service import (
    PaymentServiceError,
    PaymentStatus,
)
from plans import (
    PlanCode,
    get_plan,
)


@dataclass(
    frozen=True,
    slots=True,
)
class ActivatedSubscription:
    """Hasil pengaktifan subscription berbayar."""

    subscription_id: str
    payment_reference: str

    user_id: int
    telegram_id: int

    plan_code: PlanCode
    plan_name: str

    starts_at: datetime
    expires_at: datetime

    price_rm: str
    status: str


def parse_datetime(
    value: Any,
) -> datetime:
    """Tukar timestamptz Supabase kepada datetime UTC."""

    if not isinstance(
        value,
        str,
    ):
        raise PaymentServiceError(
            "Tarikh subscription tidak sah."
        )

    normalized_value = value.replace(
        "Z",
        "+00:00",
    )

    try:
        parsed_value = datetime.fromisoformat(
            normalized_value
        )
    except ValueError as error:
        raise PaymentServiceError(
            "Tarikh subscription tidak sah."
        ) from error

    if parsed_value.tzinfo is None:
        return parsed_value.replace(
            tzinfo=timezone.utc
        )

    return parsed_value.astimezone(
        timezone.utc
    )


def validate_payment_for_activation(
    payment: PaymentRecord,
) -> None:
    """Pastikan pembayaran boleh mengaktifkan subscription."""

    if payment.status != PaymentStatus.PAID:
        raise PaymentServiceError(
            "Pembayaran belum berstatus PAID."
        )

    if payment.plan_code == PlanCode.FREE:
        raise PaymentServiceError(
            "Pelan Free tidak memerlukan pengaktifan."
        )


def activated_subscription_from_row(
    row: dict[str, Any],
    payment: PaymentRecord,
) -> ActivatedSubscription:
    """Tukar hasil RPC kepada model pengaktifan."""

    subscription_id = row.get(
        "id"
    )

    raw_plan_code = row.get(
        "plan_code"
    )

    starts_at = row.get(
        "starts_at"
    )

    expires_at = row.get(
        "expires_at"
    )

    if (
        subscription_id is None
        or raw_plan_code is None
        or starts_at is None
        or expires_at is None
    ):
        raise PaymentServiceError(
            "Maklumat subscription tidak lengkap."
        )

    try:
        plan_code = PlanCode(
            str(raw_plan_code).upper()
        )
    except ValueError as error:
        raise PaymentServiceError(
            "Kod pelan subscription tidak sah."
        ) from error

    plan = get_plan(
        plan_code
    )

    return ActivatedSubscription(
        subscription_id=str(
            subscription_id
        ),
        payment_reference=(
            payment.payment_reference
        ),
        user_id=payment.user_id,
        telegram_id=payment.telegram_id,
        plan_code=plan_code,
        plan_name=plan.name,
        starts_at=parse_datetime(
            starts_at
        ),
        expires_at=parse_datetime(
            expires_at
        ),
        price_rm=str(
            row.get(
                "price_rm",
                payment.amount_rm,
            )
        ),
        status=str(
            row.get(
                "status",
                "ACTIVE",
            )
        ),
    )


def activate_subscription_from_payment(
    payment_reference: str,
) -> ActivatedSubscription:
    """
    Aktifkan subscription daripada pembayaran PAID.

    Fungsi database adalah atomik dan idempotent.
    """

    normalized_reference = (
        payment_reference.strip()
    )

    if not normalized_reference:
        raise PaymentServiceError(
            "Payment reference diperlukan."
        )

    payment = get_payment_by_reference(
        normalized_reference
    )

    validate_payment_for_activation(
        payment
    )

    response = supabase.rpc(
        "activate_subscription_from_payment",
        {
            "target_payment_reference": (
                normalized_reference
            ),
        },
    ).execute()

    if not response.data:
        raise PaymentServiceError(
            "Subscription gagal diaktifkan."
        )

    raw_result = response.data

    if isinstance(
        raw_result,
        list,
    ):
        if not raw_result:
            raise PaymentServiceError(
                "Subscription gagal diaktifkan."
            )

        subscription_row = raw_result[0]

    elif isinstance(
        raw_result,
        dict,
    ):
        subscription_row = raw_result

    else:
        raise PaymentServiceError(
            "Respons pengaktifan subscription tidak sah."
        )

    activated_subscription = (
        activated_subscription_from_row(
            subscription_row,
            payment,
        )
    )

    # Perlindungan tambahan jika RPC provider tidak
    # memulangkan perubahan payment dengan segera.
    refreshed_payment = get_payment_by_reference(
        normalized_reference
    )

    if (
        refreshed_payment.subscription_id
        != activated_subscription.subscription_id
    ):
        link_payment_to_subscription(
            payment_reference=normalized_reference,
            subscription_id=(
                activated_subscription.subscription_id
            ),
        )

    return activated_subscription