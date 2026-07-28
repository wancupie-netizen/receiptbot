from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any

from database import (
    get_user_by_telegram_id,
    supabase,
)
from payment_service import (
    CheckoutRequest,
    CheckoutSession,
    PaymentDetails,
    PaymentNotFoundError,
    PaymentProviderCode,
    PaymentServiceError,
    PaymentStatus,
)
from plans import PlanCode


@dataclass(
    frozen=True,
    slots=True,
)
class PaymentRecord:
    """Rekod pembayaran lengkap daripada database."""

    id: str
    payment_reference: str

    user_id: int
    telegram_id: int

    plan_code: PlanCode
    provider_code: PaymentProviderCode
    provider_reference: str | None

    amount_rm: Decimal
    currency_code: str
    status: PaymentStatus

    checkout_url: str | None

    customer_name: str
    customer_email: str | None
    customer_phone: str | None
    description: str | None

    idempotency_key: str | None
    subscription_id: str | None

    created_at: datetime
    updated_at: datetime

    expires_at: datetime | None
    paid_at: datetime | None
    failed_at: datetime | None
    cancelled_at: datetime | None
    refunded_at: datetime | None
    webhook_received_at: datetime | None

    metadata: dict[str, Any]
    provider_payload: dict[str, Any]


def utc_now() -> datetime:
    """Dapatkan waktu UTC semasa."""

    return datetime.now(
        timezone.utc
    )


def parse_datetime(
    value: Any,
) -> datetime | None:
    """Tukar nilai timestamptz Supabase kepada datetime UTC."""

    if not isinstance(
        value,
        str,
    ):
        return None

    normalized_value = value.replace(
        "Z",
        "+00:00",
    )

    try:
        parsed_value = datetime.fromisoformat(
            normalized_value
        )
    except ValueError:
        return None

    if parsed_value.tzinfo is None:
        return parsed_value.replace(
            tzinfo=timezone.utc
        )

    return parsed_value.astimezone(
        timezone.utc
    )


def require_datetime(
    value: Any,
    field_name: str,
) -> datetime:
    """Pastikan nilai datetime wajib tersedia."""

    parsed_value = parse_datetime(
        value
    )

    if parsed_value is None:
        raise PaymentServiceError(
            "Nilai tarikh pembayaran tidak sah: "
            f"{field_name}"
        )

    return parsed_value


def parse_decimal(
    value: Any,
) -> Decimal:
    """Tukar nilai database kepada Decimal."""

    try:
        return Decimal(
            str(value)
        )
    except (
        InvalidOperation,
        TypeError,
        ValueError,
    ) as error:
        raise PaymentServiceError(
            "Nilai jumlah pembayaran tidak sah."
        ) from error


def parse_json_object(
    value: Any,
) -> dict[str, Any]:
    """Pastikan nilai JSON ialah dictionary."""

    if isinstance(
        value,
        dict,
    ):
        return value

    return {}


def normalize_optional_text(
    value: Any,
) -> str | None:
    """Bersihkan nilai teks pilihan."""

    if value is None:
        return None

    normalized_value = str(
        value
    ).strip()

    if not normalized_value:
        return None

    return normalized_value


def payment_record_from_row(
    row: dict[str, Any],
) -> PaymentRecord:
    """Tukar row Supabase kepada PaymentRecord."""

    payment_id = row.get(
        "id"
    )

    payment_reference = row.get(
        "payment_reference"
    )

    user_id = row.get(
        "user_id"
    )

    telegram_id = row.get(
        "telegram_id"
    )

    if (
        payment_id is None
        or payment_reference is None
        or user_id is None
        or telegram_id is None
    ):
        raise PaymentServiceError(
            "Rekod pembayaran tidak lengkap."
        )

    try:
        plan_code = PlanCode(
            str(
                row.get("plan_code")
            ).upper()
        )
    except ValueError as error:
        raise PaymentServiceError(
            "Kod pelan pembayaran tidak sah."
        ) from error

    try:
        provider_code = PaymentProviderCode(
            str(
                row.get("provider_code")
            ).upper()
        )
    except ValueError as error:
        raise PaymentServiceError(
            "Kod penyedia pembayaran tidak sah."
        ) from error

    try:
        status = PaymentStatus(
            str(
                row.get("status")
            ).upper()
        )
    except ValueError as error:
        raise PaymentServiceError(
            "Status pembayaran tidak sah."
        ) from error

    return PaymentRecord(
        id=str(payment_id),
        payment_reference=str(
            payment_reference
        ),
        user_id=int(user_id),
        telegram_id=int(
            telegram_id
        ),
        plan_code=plan_code,
        provider_code=provider_code,
        provider_reference=normalize_optional_text(
            row.get("provider_reference")
        ),
        amount_rm=parse_decimal(
            row.get("amount_rm")
        ),
        currency_code=str(
            row.get(
                "currency_code",
                "MYR",
            )
        ),
        status=status,
        checkout_url=normalize_optional_text(
            row.get("checkout_url")
        ),
        customer_name=str(
            row.get(
                "customer_name",
                "",
            )
        ),
        customer_email=normalize_optional_text(
            row.get("customer_email")
        ),
        customer_phone=normalize_optional_text(
            row.get("customer_phone")
        ),
        description=normalize_optional_text(
            row.get("description")
        ),
        idempotency_key=normalize_optional_text(
            row.get("idempotency_key")
        ),
        subscription_id=normalize_optional_text(
            row.get("subscription_id")
        ),
        created_at=require_datetime(
            row.get("created_at"),
            "created_at",
        ),
        updated_at=require_datetime(
            row.get("updated_at"),
            "updated_at",
        ),
        expires_at=parse_datetime(
            row.get("expires_at")
        ),
        paid_at=parse_datetime(
            row.get("paid_at")
        ),
        failed_at=parse_datetime(
            row.get("failed_at")
        ),
        cancelled_at=parse_datetime(
            row.get("cancelled_at")
        ),
        refunded_at=parse_datetime(
            row.get("refunded_at")
        ),
        webhook_received_at=parse_datetime(
            row.get(
                "webhook_received_at"
            )
        ),
        metadata=parse_json_object(
            row.get("metadata")
        ),
        provider_payload=parse_json_object(
            row.get("provider_payload")
        ),
    )


def payment_details_from_record(
    record: PaymentRecord,
) -> PaymentDetails:
    """Tukar PaymentRecord kepada model PaymentDetails."""

    return PaymentDetails(
        payment_reference=(
            record.payment_reference
        ),
        provider_code=(
            record.provider_code
        ),
        telegram_id=(
            record.telegram_id
        ),
        plan_code=(
            record.plan_code
        ),
        amount_rm=(
            record.amount_rm
        ),
        status=(
            record.status
        ),
        created_at=(
            record.created_at
        ),
        paid_at=(
            record.paid_at
        ),
        failed_at=(
            record.failed_at
        ),
        cancelled_at=(
            record.cancelled_at
        ),
        refunded_at=(
            record.refunded_at
        ),
        provider_reference=(
            record.provider_reference
        ),
        metadata=(
            record.metadata
        ),
    )


def get_payment_by_reference(
    payment_reference: str,
) -> PaymentRecord:
    """Dapatkan pembayaran berdasarkan rujukan dalaman."""

    normalized_reference = (
        payment_reference.strip()
    )

    if not normalized_reference:
        raise PaymentServiceError(
            "Payment reference diperlukan."
        )

    response = (
        supabase.table("payments")
        .select("*")
        .eq(
            "payment_reference",
            normalized_reference,
        )
        .limit(1)
        .execute()
    )

    if not response.data:
        raise PaymentNotFoundError(
            "Pembayaran tidak dijumpai."
        )

    return payment_record_from_row(
        response.data[0]
    )


def find_payment_by_reference(
    payment_reference: str,
) -> PaymentRecord | None:
    """
    Cari pembayaran tanpa menghasilkan ralat
    jika rekod tidak dijumpai.
    """

    try:
        return get_payment_by_reference(
            payment_reference
        )
    except PaymentNotFoundError:
        return None


def get_payment_by_idempotency_key(
    idempotency_key: str,
) -> PaymentRecord | None:
    """Cari pembayaran melalui idempotency key."""

    normalized_key = (
        idempotency_key.strip()
    )

    if not normalized_key:
        return None

    response = (
        supabase.table("payments")
        .select("*")
        .eq(
            "idempotency_key",
            normalized_key,
        )
        .limit(1)
        .execute()
    )

    if not response.data:
        return None

    return payment_record_from_row(
        response.data[0]
    )


def create_payment_record(
    request: CheckoutRequest,
    checkout: CheckoutSession,
    idempotency_key: str | None = None,
    provider_reference: str | None = None,
    metadata: dict[str, Any] | None = None,
    provider_payload: dict[str, Any] | None = None,
) -> PaymentRecord:
    """Simpan checkout baharu ke jadual payments."""

    if (
        request.telegram_id
        != checkout.telegram_id
    ):
        raise PaymentServiceError(
            "Telegram ID checkout tidak sepadan."
        )

    if (
        request.plan_code
        != checkout.plan_code
    ):
        raise PaymentServiceError(
            "Pelan checkout tidak sepadan."
        )

    if (
        checkout.plan_code
        == PlanCode.FREE
    ):
        raise PaymentServiceError(
            "Pelan Free tidak memerlukan pembayaran."
        )

    normalized_idempotency_key = (
        normalize_optional_text(
            idempotency_key
        )
    )

    if normalized_idempotency_key:
        existing_payment = (
            get_payment_by_idempotency_key(
                normalized_idempotency_key
            )
        )

        if existing_payment is not None:
            return existing_payment

    existing_reference = find_payment_by_reference(
        checkout.payment_reference
    )

    if existing_reference is not None:
        return existing_reference

    user = get_user_by_telegram_id(
        request.telegram_id
    )

    user_id = user.get(
        "id"
    )

    if user_id is None:
        raise PaymentServiceError(
            "User ID tidak dijumpai."
        )

    combined_metadata: dict[
        str,
        Any,
    ] = {
        "return_url": (
            request.return_url
        ),
        "callback_url": (
            request.callback_url
        ),
    }

    if metadata:
        combined_metadata.update(
            metadata
        )

    insert_data = {
        "payment_reference": (
            checkout.payment_reference
        ),
        "user_id": int(
            user_id
        ),
        "telegram_id": (
            request.telegram_id
        ),
        "plan_code": (
            checkout.plan_code.value
        ),
        "subscription_id": None,
        "provider_code": (
            checkout.provider_code.value
        ),
        "provider_reference": (
            normalize_optional_text(
                provider_reference
            )
        ),
        "amount_rm": str(
            checkout.amount_rm
        ),
        "currency_code": "MYR",
        "status": (
            checkout.status.value
        ),
        "checkout_url": (
            checkout.checkout_url
        ),
        "customer_name": (
            request.customer_name
        ),
        "customer_email": (
            normalize_optional_text(
                request.customer_email
            )
        ),
        "customer_phone": (
            normalize_optional_text(
                request.customer_phone
            )
        ),
        "description": (
            normalize_optional_text(
                request.description
            )
        ),
        "idempotency_key": (
            normalized_idempotency_key
        ),
        "expires_at": (
            checkout.expires_at.isoformat()
            if checkout.expires_at
            else None
        ),
        "metadata": (
            combined_metadata
        ),
        "provider_payload": (
            provider_payload or {}
        ),
    }

    response = (
        supabase.table("payments")
        .insert(
            insert_data
        )
        .execute()
    )

    if not response.data:
        raise PaymentServiceError(
            "Rekod pembayaran gagal disimpan."
        )

    return payment_record_from_row(
        response.data[0]
    )


def list_user_payments(
    telegram_id: int,
    limit: int = 10,
) -> list[PaymentRecord]:
    """Senaraikan transaksi terkini pengguna."""

    safe_limit = max(
        1,
        min(
            limit,
            50,
        ),
    )

    response = (
        supabase.table("payments")
        .select("*")
        .eq(
            "telegram_id",
            telegram_id,
        )
        .order(
            "created_at",
            desc=True,
        )
        .limit(
            safe_limit
        )
        .execute()
    )

    return [
        payment_record_from_row(
            row
        )
        for row in (
            response.data or []
        )
    ]


def get_latest_pending_payment(
    telegram_id: int,
    plan_code: PlanCode | None = None,
) -> PaymentRecord | None:
    """Dapatkan pembayaran PENDING terbaru pengguna."""

    query = (
        supabase.table("payments")
        .select("*")
        .eq(
            "telegram_id",
            telegram_id,
        )
        .eq(
            "status",
            PaymentStatus.PENDING.value,
        )
    )

    if plan_code is not None:
        query = query.eq(
            "plan_code",
            plan_code.value,
        )

    response = (
        query.order(
            "created_at",
            desc=True,
        )
        .limit(1)
        .execute()
    )

    if not response.data:
        return None

    return payment_record_from_row(
        response.data[0]
    )


def update_payment_gateway_data(
    payment_reference: str,
    provider_reference: str | None = None,
    checkout_url: str | None = None,
    expires_at: datetime | None = None,
    provider_payload: dict[str, Any] | None = None,
) -> PaymentRecord:
    """Kemas kini data yang diterima daripada gateway."""

    update_data: dict[
        str,
        Any,
    ] = {}

    if provider_reference is not None:
        update_data[
            "provider_reference"
        ] = normalize_optional_text(
            provider_reference
        )

    if checkout_url is not None:
        update_data[
            "checkout_url"
        ] = normalize_optional_text(
            checkout_url
        )

    if expires_at is not None:
        update_data[
            "expires_at"
        ] = expires_at.isoformat()

    if provider_payload is not None:
        update_data[
            "provider_payload"
        ] = provider_payload

    if not update_data:
        return get_payment_by_reference(
            payment_reference
        )

    response = (
        supabase.table("payments")
        .update(
            update_data
        )
        .eq(
            "payment_reference",
            payment_reference.strip(),
        )
        .execute()
    )

    if not response.data:
        raise PaymentNotFoundError(
            "Pembayaran tidak dijumpai."
        )

    return payment_record_from_row(
        response.data[0]
    )


def update_payment_status(
    payment_reference: str,
    new_status: PaymentStatus,
    provider_reference: str | None = None,
    provider_payload: dict[str, Any] | None = None,
    webhook_received_at: datetime | None = None,
) -> PaymentRecord:
    """Kemas kini status dan timestamp pembayaran."""

    existing_payment = get_payment_by_reference(
        payment_reference
    )

    if (
        existing_payment.status
        == new_status
    ):
        return existing_payment

    update_data: dict[
        str,
        Any,
    ] = {
        "status": new_status.value,
    }

    current_time = utc_now()

    if new_status == PaymentStatus.PAID:
        update_data[
            "paid_at"
        ] = current_time.isoformat()

    elif new_status == PaymentStatus.FAILED:
        update_data[
            "failed_at"
        ] = current_time.isoformat()

    elif new_status == PaymentStatus.CANCELLED:
        update_data[
            "cancelled_at"
        ] = current_time.isoformat()

    elif new_status == PaymentStatus.REFUNDED:
        if existing_payment.paid_at is None:
            raise PaymentServiceError(
                "Pembayaran belum pernah dibayar."
            )

        update_data[
            "refunded_at"
        ] = current_time.isoformat()

    if provider_reference is not None:
        update_data[
            "provider_reference"
        ] = normalize_optional_text(
            provider_reference
        )

    if provider_payload is not None:
        update_data[
            "provider_payload"
        ] = provider_payload

    if webhook_received_at is not None:
        update_data[
            "webhook_received_at"
        ] = webhook_received_at.isoformat()

    response = (
        supabase.table("payments")
        .update(
            update_data
        )
        .eq(
            "payment_reference",
            payment_reference.strip(),
        )
        .execute()
    )

    if not response.data:
        raise PaymentNotFoundError(
            "Pembayaran tidak dijumpai."
        )

    return payment_record_from_row(
        response.data[0]
    )


def mark_payment_paid(
    payment_reference: str,
    provider_reference: str | None = None,
    provider_payload: dict[str, Any] | None = None,
    webhook_received_at: datetime | None = None,
) -> PaymentRecord:
    """Tandakan pembayaran sebagai PAID."""

    return update_payment_status(
        payment_reference=payment_reference,
        new_status=PaymentStatus.PAID,
        provider_reference=provider_reference,
        provider_payload=provider_payload,
        webhook_received_at=(
            webhook_received_at
        ),
    )


def mark_payment_failed(
    payment_reference: str,
    provider_reference: str | None = None,
    provider_payload: dict[str, Any] | None = None,
    webhook_received_at: datetime | None = None,
) -> PaymentRecord:
    """Tandakan pembayaran sebagai FAILED."""

    return update_payment_status(
        payment_reference=payment_reference,
        new_status=PaymentStatus.FAILED,
        provider_reference=provider_reference,
        provider_payload=provider_payload,
        webhook_received_at=(
            webhook_received_at
        ),
    )


def cancel_payment_record(
    payment_reference: str,
) -> PaymentRecord:
    """Batalkan rekod pembayaran PENDING."""

    existing_payment = get_payment_by_reference(
        payment_reference
    )

    if existing_payment.status == PaymentStatus.PAID:
        raise PaymentServiceError(
            "Pembayaran yang telah dibayar "
            "tidak boleh dibatalkan."
        )

    if (
        existing_payment.status
        == PaymentStatus.REFUNDED
    ):
        raise PaymentServiceError(
            "Pembayaran yang dipulangkan "
            "tidak boleh dibatalkan."
        )

    return update_payment_status(
        payment_reference=payment_reference,
        new_status=PaymentStatus.CANCELLED,
    )


def refund_payment_record(
    payment_reference: str,
    provider_payload: dict[str, Any] | None = None,
) -> PaymentRecord:
    """Tandakan pembayaran PAID sebagai REFUNDED."""

    existing_payment = get_payment_by_reference(
        payment_reference
    )

    if existing_payment.status != PaymentStatus.PAID:
        raise PaymentServiceError(
            "Hanya pembayaran PAID "
            "boleh dipulangkan."
        )

    return update_payment_status(
        payment_reference=payment_reference,
        new_status=PaymentStatus.REFUNDED,
        provider_payload=provider_payload,
    )


def link_payment_to_subscription(
    payment_reference: str,
    subscription_id: str,
) -> PaymentRecord:
    """Pautkan pembayaran berjaya kepada subscription."""

    normalized_subscription_id = (
        subscription_id.strip()
    )

    if not normalized_subscription_id:
        raise PaymentServiceError(
            "Subscription ID diperlukan."
        )

    payment = get_payment_by_reference(
        payment_reference
    )

    if payment.status not in {
        PaymentStatus.PAID,
        PaymentStatus.REFUNDED,
    }:
        raise PaymentServiceError(
            "Hanya pembayaran berjaya boleh "
            "dipautkan kepada subscription."
        )

    response = (
        supabase.table("payments")
        .update(
            {
                "subscription_id": (
                    normalized_subscription_id
                ),
            }
        )
        .eq(
            "payment_reference",
            payment_reference.strip(),
        )
        .execute()
    )

    if not response.data:
        raise PaymentNotFoundError(
            "Pembayaran tidak dijumpai."
        )

    return payment_record_from_row(
        response.data[0]
    )


def record_webhook_received(
    payment_reference: str,
    provider_payload: dict[str, Any],
) -> PaymentRecord:
    """Rekod masa dan payload webhook terakhir."""

    response = (
        supabase.table("payments")
        .update(
            {
                "webhook_received_at": (
                    utc_now().isoformat()
                ),
                "provider_payload": (
                    provider_payload
                ),
            }
        )
        .eq(
            "payment_reference",
            payment_reference.strip(),
        )
        .execute()
    )

    if not response.data:
        raise PaymentNotFoundError(
            "Pembayaran tidak dijumpai."
        )

    return payment_record_from_row(
        response.data[0]
    )