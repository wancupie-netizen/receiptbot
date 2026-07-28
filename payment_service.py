from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from enum import StrEnum
from typing import Protocol
from uuid import uuid4

from plans import (
    Plan,
    PlanCode,
    get_plan,
)


class PaymentStatus(StrEnum):
    """Status rasmi pembayaran ReceiptBot."""

    PENDING = "PENDING"
    PAID = "PAID"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    REFUNDED = "REFUNDED"


class PaymentProviderCode(StrEnum):
    """Kod rasmi penyedia pembayaran."""

    NOT_CONFIGURED = "NOT_CONFIGURED"
    DEVELOPMENT = "DEVELOPMENT"
    BILLPLZ = "BILLPLZ"
    BAYARCASH = "BAYARCASH"


class PaymentServiceError(RuntimeError):
    """Ralat asas Payment Service."""


class PaymentProviderNotConfiguredError(
    PaymentServiceError
):
    """Payment gateway belum dikonfigurasi."""


class InvalidPaymentPlanError(
    PaymentServiceError
):
    """Pelan tidak sah untuk pembayaran."""


class PaymentNotFoundError(
    PaymentServiceError
):
    """Rekod pembayaran tidak dijumpai."""


@dataclass(
    frozen=True,
    slots=True,
)
class CheckoutRequest:
    """Maklumat yang diperlukan untuk checkout."""

    telegram_id: int
    plan_code: PlanCode

    customer_name: str
    customer_email: str | None = None
    customer_phone: str | None = None

    return_url: str | None = None
    callback_url: str | None = None

    description: str | None = None


@dataclass(
    frozen=True,
    slots=True,
)
class CheckoutSession:
    """Keputusan selepas checkout dicipta."""

    payment_reference: str
    provider_code: PaymentProviderCode

    telegram_id: int
    plan_code: PlanCode

    amount_rm: Decimal
    status: PaymentStatus

    checkout_url: str

    created_at: datetime
    expires_at: datetime | None = None


@dataclass(
    frozen=True,
    slots=True,
)
class PaymentDetails:
    """Maklumat semasa sesuatu pembayaran."""

    payment_reference: str
    provider_code: PaymentProviderCode

    telegram_id: int
    plan_code: PlanCode

    amount_rm: Decimal
    status: PaymentStatus

    created_at: datetime

    paid_at: datetime | None = None
    failed_at: datetime | None = None
    cancelled_at: datetime | None = None
    refunded_at: datetime | None = None

    provider_reference: str | None = None
    metadata: dict[str, object] | None = None


class PaymentGateway(Protocol):
    """Kontrak yang wajib dipenuhi payment gateway."""

    provider_code: PaymentProviderCode

    def create_checkout(
        self,
        request: CheckoutRequest,
        plan: Plan,
    ) -> CheckoutSession:
        """Cipta sesi pembayaran."""

        ...

    def get_payment_status(
        self,
        payment_reference: str,
    ) -> PaymentDetails:
        """Dapatkan status pembayaran daripada gateway."""

        ...

    def cancel_payment(
        self,
        payment_reference: str,
    ) -> PaymentDetails:
        """Batalkan pembayaran pada gateway."""

        ...

    def refund_payment(
        self,
        payment_reference: str,
    ) -> PaymentDetails:
        """Pulangkan pembayaran pada gateway."""

        ...


class NotConfiguredPaymentGateway:
    """Gateway lalai sebelum provider sebenar dipasang."""

    provider_code = (
        PaymentProviderCode.NOT_CONFIGURED
    )

    def create_checkout(
        self,
        request: CheckoutRequest,
        plan: Plan,
    ) -> CheckoutSession:
        raise PaymentProviderNotConfiguredError(
            "Payment gateway belum dikonfigurasi."
        )

    def get_payment_status(
        self,
        payment_reference: str,
    ) -> PaymentDetails:
        raise PaymentProviderNotConfiguredError(
            "Payment gateway belum dikonfigurasi."
        )

    def cancel_payment(
        self,
        payment_reference: str,
    ) -> PaymentDetails:
        raise PaymentProviderNotConfiguredError(
            "Payment gateway belum dikonfigurasi."
        )

    def refund_payment(
        self,
        payment_reference: str,
    ) -> PaymentDetails:
        raise PaymentProviderNotConfiguredError(
            "Payment gateway belum dikonfigurasi."
        )


class DevelopmentPaymentGateway:
    """
    Gateway pembangunan untuk ujian tempatan.

    Gateway ini tidak menerima bayaran sebenar dan tidak
    boleh digunakan dalam production.
    """

    provider_code = (
        PaymentProviderCode.DEVELOPMENT
    )

    def __init__(self) -> None:
        self._payments: dict[
            str,
            PaymentDetails,
        ] = {}

    def create_checkout(
        self,
        request: CheckoutRequest,
        plan: Plan,
    ) -> CheckoutSession:
        """Cipta checkout pembangunan."""

        payment_reference = (
            f"dev_{uuid4().hex}"
        )

        created_at = datetime.now(
            timezone.utc
        )

        payment = PaymentDetails(
            payment_reference=payment_reference,
            provider_code=self.provider_code,
            telegram_id=request.telegram_id,
            plan_code=request.plan_code,
            amount_rm=plan.monthly_price_rm,
            status=PaymentStatus.PENDING,
            created_at=created_at,
            metadata={
                "customer_name": (
                    request.customer_name
                ),
                "customer_email": (
                    request.customer_email
                ),
                "customer_phone": (
                    request.customer_phone
                ),
                "description": (
                    request.description
                ),
            },
        )

        self._payments[
            payment_reference
        ] = payment

        return CheckoutSession(
            payment_reference=payment_reference,
            provider_code=self.provider_code,
            telegram_id=request.telegram_id,
            plan_code=request.plan_code,
            amount_rm=plan.monthly_price_rm,
            status=PaymentStatus.PENDING,
            checkout_url=(
                "https://example.invalid/"
                f"checkout/{payment_reference}"
            ),
            created_at=created_at,
            expires_at=None,
        )

    def get_payment_status(
        self,
        payment_reference: str,
    ) -> PaymentDetails:
        """Baca pembayaran dalam memori pembangunan."""

        payment = self._payments.get(
            payment_reference
        )

        if payment is None:
            raise PaymentNotFoundError(
                "Pembayaran tidak dijumpai "
                "dalam Development Gateway."
            )

        return payment

    def mark_payment_paid(
        self,
        payment_reference: str,
    ) -> PaymentDetails:
        """Tandakan pembayaran ujian sebagai PAID."""

        payment = self.get_payment_status(
            payment_reference
        )

        updated_payment = PaymentDetails(
            payment_reference=(
                payment.payment_reference
            ),
            provider_code=(
                payment.provider_code
            ),
            telegram_id=(
                payment.telegram_id
            ),
            plan_code=(
                payment.plan_code
            ),
            amount_rm=(
                payment.amount_rm
            ),
            status=PaymentStatus.PAID,
            created_at=(
                payment.created_at
            ),
            paid_at=datetime.now(
                timezone.utc
            ),
            provider_reference=(
                payment.provider_reference
            ),
            metadata=(
                payment.metadata
            ),
        )

        self._payments[
            payment_reference
        ] = updated_payment

        return updated_payment

    def mark_payment_failed(
        self,
        payment_reference: str,
    ) -> PaymentDetails:
        """Tandakan pembayaran ujian sebagai FAILED."""

        payment = self.get_payment_status(
            payment_reference
        )

        updated_payment = PaymentDetails(
            payment_reference=(
                payment.payment_reference
            ),
            provider_code=(
                payment.provider_code
            ),
            telegram_id=(
                payment.telegram_id
            ),
            plan_code=(
                payment.plan_code
            ),
            amount_rm=(
                payment.amount_rm
            ),
            status=PaymentStatus.FAILED,
            created_at=(
                payment.created_at
            ),
            failed_at=datetime.now(
                timezone.utc
            ),
            provider_reference=(
                payment.provider_reference
            ),
            metadata=(
                payment.metadata
            ),
        )

        self._payments[
            payment_reference
        ] = updated_payment

        return updated_payment

    def cancel_payment(
        self,
        payment_reference: str,
    ) -> PaymentDetails:
        """Batalkan pembayaran ujian."""

        payment = self.get_payment_status(
            payment_reference
        )

        if payment.status == PaymentStatus.PAID:
            raise PaymentServiceError(
                "Pembayaran yang telah dibayar "
                "tidak boleh dibatalkan."
            )

        if (
            payment.status
            == PaymentStatus.REFUNDED
        ):
            raise PaymentServiceError(
                "Pembayaran yang telah dipulangkan "
                "tidak boleh dibatalkan."
            )

        updated_payment = PaymentDetails(
            payment_reference=(
                payment.payment_reference
            ),
            provider_code=(
                payment.provider_code
            ),
            telegram_id=(
                payment.telegram_id
            ),
            plan_code=(
                payment.plan_code
            ),
            amount_rm=(
                payment.amount_rm
            ),
            status=PaymentStatus.CANCELLED,
            created_at=(
                payment.created_at
            ),
            cancelled_at=datetime.now(
                timezone.utc
            ),
            provider_reference=(
                payment.provider_reference
            ),
            metadata=(
                payment.metadata
            ),
        )

        self._payments[
            payment_reference
        ] = updated_payment

        return updated_payment

    def refund_payment(
        self,
        payment_reference: str,
    ) -> PaymentDetails:
        """Pulangkan pembayaran ujian."""

        payment = self.get_payment_status(
            payment_reference
        )

        if payment.status != PaymentStatus.PAID:
            raise PaymentServiceError(
                "Hanya pembayaran PAID "
                "boleh dipulangkan."
            )

        updated_payment = PaymentDetails(
            payment_reference=(
                payment.payment_reference
            ),
            provider_code=(
                payment.provider_code
            ),
            telegram_id=(
                payment.telegram_id
            ),
            plan_code=(
                payment.plan_code
            ),
            amount_rm=(
                payment.amount_rm
            ),
            status=PaymentStatus.REFUNDED,
            created_at=(
                payment.created_at
            ),
            paid_at=(
                payment.paid_at
            ),
            refunded_at=datetime.now(
                timezone.utc
            ),
            provider_reference=(
                payment.provider_reference
            ),
            metadata=(
                payment.metadata
            ),
        )

        self._payments[
            payment_reference
        ] = updated_payment

        return updated_payment


_payment_gateway: PaymentGateway = (
    NotConfiguredPaymentGateway()
)


def configure_payment_gateway(
    gateway: PaymentGateway,
) -> None:
    """Tetapkan payment gateway yang akan digunakan."""

    global _payment_gateway

    _payment_gateway = gateway


def get_payment_gateway() -> PaymentGateway:
    """Dapatkan payment gateway semasa."""

    return _payment_gateway


def validate_paid_plan(
    plan_code: PlanCode | str,
) -> Plan:
    """Pastikan pelan boleh dibeli."""

    try:
        normalized_plan_code = PlanCode(
            str(plan_code).upper()
        )
    except ValueError as error:
        raise InvalidPaymentPlanError(
            f"Pelan tidak dikenali: {plan_code}"
        ) from error

    if normalized_plan_code == PlanCode.FREE:
        raise InvalidPaymentPlanError(
            "Pelan Free tidak memerlukan pembayaran."
        )

    plan = get_plan(
        normalized_plan_code
    )

    if plan.monthly_price_rm <= 0:
        raise InvalidPaymentPlanError(
            "Harga pelan tidak sah."
        )

    return plan


def validate_checkout_request(
    request: CheckoutRequest,
) -> None:
    """Sahkan maklumat asas checkout."""

    if request.telegram_id <= 0:
        raise PaymentServiceError(
            "Telegram ID tidak sah."
        )

    if not request.customer_name.strip():
        raise PaymentServiceError(
            "Nama pelanggan diperlukan."
        )


def validate_payment_reference(
    payment_reference: str,
) -> str:
    """Sahkan dan bersihkan payment reference."""

    normalized_reference = (
        payment_reference.strip()
    )

    if not normalized_reference:
        raise PaymentServiceError(
            "Payment reference diperlukan."
        )

    return normalized_reference


def create_checkout(
    request: CheckoutRequest,
    idempotency_key: str | None = None,
) -> CheckoutSession:
    """
    Cipta checkout dan simpan transaksi ke Supabase.

    Jika idempotency_key sudah wujud, transaksi lama
    akan digunakan semula.
    """

    validate_checkout_request(
        request
    )

    plan = validate_paid_plan(
        request.plan_code
    )

    normalized_idempotency_key = None

    if idempotency_key is not None:
        normalized_idempotency_key = (
            idempotency_key.strip()
        )

        if not normalized_idempotency_key:
            normalized_idempotency_key = None

    # Import di dalam fungsi untuk mengelakkan
    # circular import dengan payment_repository.py.
    from payment_repository import (
        get_payment_by_idempotency_key,
    )

    if normalized_idempotency_key is not None:
        existing_payment = (
            get_payment_by_idempotency_key(
                normalized_idempotency_key
            )
        )

        if existing_payment is not None:
            if (
                existing_payment.telegram_id
                != request.telegram_id
            ):
                raise PaymentServiceError(
                    "Idempotency key telah digunakan "
                    "oleh pengguna lain."
                )

            if (
                existing_payment.plan_code
                != request.plan_code
            ):
                raise PaymentServiceError(
                    "Idempotency key telah digunakan "
                    "untuk pelan yang berbeza."
                )

            if existing_payment.checkout_url is None:
                raise PaymentServiceError(
                    "Transaksi lama tidak mempunyai "
                    "checkout URL."
                )

            return CheckoutSession(
                payment_reference=(
                    existing_payment
                    .payment_reference
                ),
                provider_code=(
                    existing_payment
                    .provider_code
                ),
                telegram_id=(
                    existing_payment
                    .telegram_id
                ),
                plan_code=(
                    existing_payment
                    .plan_code
                ),
                amount_rm=(
                    existing_payment
                    .amount_rm
                ),
                status=(
                    existing_payment
                    .status
                ),
                checkout_url=(
                    existing_payment
                    .checkout_url
                ),
                created_at=(
                    existing_payment
                    .created_at
                ),
                expires_at=(
                    existing_payment
                    .expires_at
                ),
            )

    gateway = get_payment_gateway()

    checkout = gateway.create_checkout(
        request=request,
        plan=plan,
    )

    if checkout.status != PaymentStatus.PENDING:
        raise PaymentServiceError(
            "Checkout baharu mesti bermula "
            "dengan status PENDING."
        )

    if checkout.amount_rm != plan.monthly_price_rm:
        raise PaymentServiceError(
            "Jumlah checkout tidak sepadan "
            "dengan harga pelan."
        )

    from payment_repository import (
        create_payment_record,
    )

    payment_record = create_payment_record(
        request=request,
        checkout=checkout,
        idempotency_key=(
            normalized_idempotency_key
        ),
        metadata={
            "service": "payment_service",
        },
    )

    if payment_record.checkout_url is None:
        raise PaymentServiceError(
            "Checkout URL gagal disimpan."
        )

    return CheckoutSession(
        payment_reference=(
            payment_record.payment_reference
        ),
        provider_code=(
            payment_record.provider_code
        ),
        telegram_id=(
            payment_record.telegram_id
        ),
        plan_code=(
            payment_record.plan_code
        ),
        amount_rm=(
            payment_record.amount_rm
        ),
        status=(
            payment_record.status
        ),
        checkout_url=(
            payment_record.checkout_url
        ),
        created_at=(
            payment_record.created_at
        ),
        expires_at=(
            payment_record.expires_at
        ),
    )


def get_payment_status(
    payment_reference: str,
) -> PaymentDetails:
    """
    Dapatkan status pembayaran daripada Supabase.

    Database ialah sumber kebenaran utama.
    """

    normalized_reference = (
        validate_payment_reference(
            payment_reference
        )
    )

    from payment_repository import (
        get_payment_by_reference,
        payment_details_from_record,
    )

    payment_record = get_payment_by_reference(
        normalized_reference
    )

    return payment_details_from_record(
        payment_record
    )


def sync_payment_status_from_gateway(
    payment_reference: str,
) -> PaymentDetails:
    """
    Baca status terkini daripada gateway dan simpan
    perubahan ke Supabase.

    Fungsi ini akan digunakan oleh gateway sebenar nanti.
    """

    normalized_reference = (
        validate_payment_reference(
            payment_reference
        )
    )

    gateway = get_payment_gateway()

    gateway_payment = (
        gateway.get_payment_status(
            normalized_reference
        )
    )

    from payment_repository import (
        payment_details_from_record,
        update_payment_status,
    )

    updated_record = update_payment_status(
        payment_reference=normalized_reference,
        new_status=gateway_payment.status,
        provider_reference=(
            gateway_payment.provider_reference
        ),
        provider_payload={
            "source": "gateway_sync",
            "provider_code": (
                gateway_payment
                .provider_code
                .value
            ),
        },
    )

    return payment_details_from_record(
        updated_record
    )


def cancel_payment(
    payment_reference: str,
) -> PaymentDetails:
    """Batalkan pembayaran pada gateway dan database."""

    normalized_reference = (
        validate_payment_reference(
            payment_reference
        )
    )

    current_payment = get_payment_status(
        normalized_reference
    )

    if current_payment.status == PaymentStatus.PAID:
        raise PaymentServiceError(
            "Pembayaran yang telah dibayar "
            "tidak boleh dibatalkan."
        )

    if (
        current_payment.status
        == PaymentStatus.REFUNDED
    ):
        raise PaymentServiceError(
            "Pembayaran yang telah dipulangkan "
            "tidak boleh dibatalkan."
        )

    if (
        current_payment.status
        == PaymentStatus.CANCELLED
    ):
        return current_payment

    gateway = get_payment_gateway()

    gateway_payment = gateway.cancel_payment(
        normalized_reference
    )

    from payment_repository import (
        cancel_payment_record,
        payment_details_from_record,
    )

    cancelled_record = cancel_payment_record(
        normalized_reference
    )

    result = payment_details_from_record(
        cancelled_record
    )

    if (
        gateway_payment.status
        != PaymentStatus.CANCELLED
    ):
        raise PaymentServiceError(
            "Gateway tidak memulangkan "
            "status CANCELLED."
        )

    return result


def refund_payment(
    payment_reference: str,
) -> PaymentDetails:
    """Pulangkan pembayaran pada gateway dan database."""

    normalized_reference = (
        validate_payment_reference(
            payment_reference
        )
    )

    current_payment = get_payment_status(
        normalized_reference
    )

    if (
        current_payment.status
        == PaymentStatus.REFUNDED
    ):
        return current_payment

    if current_payment.status != PaymentStatus.PAID:
        raise PaymentServiceError(
            "Hanya pembayaran PAID "
            "boleh dipulangkan."
        )

    gateway = get_payment_gateway()

    gateway_payment = gateway.refund_payment(
        normalized_reference
    )

    from payment_repository import (
        payment_details_from_record,
        refund_payment_record,
    )

    refunded_record = refund_payment_record(
        payment_reference=(
            normalized_reference
        ),
        provider_payload={
            "source": "payment_service",
            "gateway_status": (
                gateway_payment.status.value
            ),
        },
    )

    result = payment_details_from_record(
        refunded_record
    )

    if (
        gateway_payment.status
        != PaymentStatus.REFUNDED
    ):
        raise PaymentServiceError(
            "Gateway tidak memulangkan "
            "status REFUNDED."
        )

    return result


def mark_development_payment_paid(
    payment_reference: str,
) -> PaymentDetails:
    """
    Tandakan transaksi Development sebagai PAID.

    Fungsi ini untuk ujian tempatan sahaja.
    """

    normalized_reference = (
        validate_payment_reference(
            payment_reference
        )
    )

    gateway = get_payment_gateway()

    if not isinstance(
        gateway,
        DevelopmentPaymentGateway,
    ):
        raise PaymentServiceError(
            "Fungsi ini hanya boleh digunakan "
            "dengan Development Gateway."
        )

    gateway_payment = (
        gateway.mark_payment_paid(
            normalized_reference
        )
    )

    from payment_repository import (
        mark_payment_paid,
        payment_details_from_record,
    )

    paid_record = mark_payment_paid(
        payment_reference=(
            normalized_reference
        ),
        provider_reference=(
            gateway_payment
            .provider_reference
            or f"dev_paid_{uuid4().hex}"
        ),
        provider_payload={
            "source": "development_gateway",
            "status": "PAID",
        },
    )

    return payment_details_from_record(
        paid_record
    )


def mark_development_payment_failed(
    payment_reference: str,
) -> PaymentDetails:
    """
    Tandakan transaksi Development sebagai FAILED.

    Fungsi ini untuk ujian tempatan sahaja.
    """

    normalized_reference = (
        validate_payment_reference(
            payment_reference
        )
    )

    gateway = get_payment_gateway()

    if not isinstance(
        gateway,
        DevelopmentPaymentGateway,
    ):
        raise PaymentServiceError(
            "Fungsi ini hanya boleh digunakan "
            "dengan Development Gateway."
        )

    gateway_payment = (
        gateway.mark_payment_failed(
            normalized_reference
        )
    )

    from payment_repository import (
        mark_payment_failed,
        payment_details_from_record,
    )

    failed_record = mark_payment_failed(
        payment_reference=(
            normalized_reference
        ),
        provider_reference=(
            gateway_payment
            .provider_reference
        ),
        provider_payload={
            "source": "development_gateway",
            "status": "FAILED",
        },
    )

    return payment_details_from_record(
        failed_record
    )