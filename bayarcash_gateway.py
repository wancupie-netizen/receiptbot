import hashlib
import hmac
import logging
import re
from dataclasses import dataclass
from decimal import (
    Decimal,
    InvalidOperation,
)
from typing import Any, Iterable

import httpx

from payment_config import (
    BayarCashConfig,
)


logger = logging.getLogger(__name__)


class BayarCashError(RuntimeError):
    """Ralat asas adapter BayarCash."""


class BayarCashValidationError(
    BayarCashError
):
    """Data Payment Intent tidak sah."""


class BayarCashAuthenticationError(
    BayarCashError
):
    """Credential BayarCash ditolak."""


class BayarCashNotFoundError(
    BayarCashError
):
    """Resource BayarCash tidak dijumpai."""


class BayarCashRateLimitError(
    BayarCashError
):
    """Had permintaan BayarCash telah dicapai."""


class BayarCashAPIError(
    BayarCashError
):
    """BayarCash memulangkan ralat API."""


@dataclass(
    frozen=True,
    slots=True,
)
class BayarCashPaymentIntentRequest:
    """Maklumat untuk mencipta Payment Intent."""

    order_number: str
    amount: Decimal

    payer_name: str
    payer_email: str

    payer_telephone_number: str | None = None

    payment_channel: (
        int
        | tuple[int, ...]
        | None
    ) = None

    return_url: str | None = None
    callback_url: str | None = None

    metadata: dict[str, Any] | None = None


@dataclass(
    frozen=True,
    slots=True,
)
class BayarCashPaymentIntent:
    """Payment Intent yang dipulangkan BayarCash."""

    payment_intent_id: str
    order_number: str | None

    amount: Decimal | None
    status: str | int | None

    checkout_url: str

    raw_payload: dict[str, Any]


def normalize_amount(
    raw_amount: Decimal | str | int | float,
) -> Decimal:
    """Format jumlah kepada dua titik perpuluhan."""

    try:
        amount = Decimal(
            str(raw_amount)
        ).quantize(
            Decimal("0.01")
        )

    except (
        InvalidOperation,
        TypeError,
        ValueError,
    ) as error:
        raise BayarCashValidationError(
            "Jumlah pembayaran tidak sah."
        ) from error

    if amount < Decimal("1.00"):
        raise BayarCashValidationError(
            "Jumlah minimum Payment Intent "
            "ialah RM1.00."
        )

    if amount > Decimal("30000.00"):
        raise BayarCashValidationError(
            "Jumlah Payment Intent melebihi "
            "had RM30,000.00."
        )

    return amount


def normalize_order_number(
    raw_order_number: str,
) -> str:
    """Sahkan order number BayarCash."""

    order_number = (
        raw_order_number.strip()
    )

    if not order_number:
        raise BayarCashValidationError(
            "Order number diperlukan."
        )

    if len(order_number) > 30:
        raise BayarCashValidationError(
            "Order number BayarCash "
            "tidak boleh melebihi 30 aksara."
        )

    if not re.fullmatch(
        r"[A-Za-z0-9._\-]+",
        order_number,
    ):
        raise BayarCashValidationError(
            "Order number hanya boleh mengandungi "
            "huruf, nombor, titik, sengkang atau "
            "garis bawah."
        )

    return order_number


def normalize_payer_name(
    raw_name: str,
) -> str:
    """Sahkan nama pembayar."""

    payer_name = raw_name.strip()

    if len(payer_name) < 2:
        raise BayarCashValidationError(
            "Nama pembayar tidak sah."
        )

    if len(payer_name) > 150:
        raise BayarCashValidationError(
            "Nama pembayar tidak boleh "
            "melebihi 150 aksara."
        )

    return payer_name


def normalize_payer_email(
    raw_email: str,
) -> str:
    """Sahkan email pembayar."""

    payer_email = (
        raw_email.strip().lower()
    )

    if len(payer_email) > 250:
        raise BayarCashValidationError(
            "Email pembayar tidak boleh "
            "melebihi 250 aksara."
        )

    if not re.fullmatch(
        (
            r"[A-Za-z0-9._%+\-]+@"
            r"[A-Za-z0-9.\-]+\."
            r"[A-Za-z]{2,}"
        ),
        payer_email,
    ):
        raise BayarCashValidationError(
            "Email pembayar tidak sah."
        )

    return payer_email


def normalize_phone_number(
    raw_phone_number: str | None,
) -> str | None:
    """Bersihkan nombor telefon pembayar."""

    if raw_phone_number is None:
        return None

    phone_number = re.sub(
        r"[^\d+]",
        "",
        raw_phone_number.strip(),
    )

    if not phone_number:
        return None

    if len(phone_number) > 20:
        raise BayarCashValidationError(
            "Nombor telefon tidak boleh "
            "melebihi 20 aksara."
        )

    if not re.fullmatch(
        r"\+?[0-9]{8,15}",
        phone_number,
    ):
        raise BayarCashValidationError(
            "Nombor telefon pembayar tidak sah."
        )

    return phone_number


def normalize_payment_channels(
    raw_channels: (
        int
        | Iterable[int]
        | None
    ),
    default_channel: int,
) -> tuple[int, ...]:
    """Sahkan satu atau beberapa payment channel."""

    if raw_channels is None:
        channels = (
            default_channel,
        )

    elif isinstance(
        raw_channels,
        int,
    ):
        channels = (
            raw_channels,
        )

    else:
        channels = tuple(
            raw_channels
        )

    if not channels:
        raise BayarCashValidationError(
            "Sekurang-kurangnya satu "
            "payment channel diperlukan."
        )

    normalized_channels: list[int] = []

    for channel in channels:
        try:
            normalized_channel = int(
                channel
            )
        except (
            TypeError,
            ValueError,
        ) as error:
            raise BayarCashValidationError(
                "Payment channel tidak sah."
            ) from error

        if normalized_channel <= 0:
            raise BayarCashValidationError(
                "Payment channel mesti lebih "
                "besar daripada sifar."
            )

        if (
            normalized_channel
            not in normalized_channels
        ):
            normalized_channels.append(
                normalized_channel
            )

    return tuple(
        normalized_channels
    )


def format_checksum_payment_channel(
    payment_channels: tuple[int, ...],
) -> str:
    """Format channel seperti SDK rasmi BayarCash."""

    return ",".join(
        str(channel)
        for channel in payment_channels
    )


def create_payment_intent_checksum(
    api_secret_key: str,
    payment_channels: tuple[int, ...],
    order_number: str,
    amount: Decimal,
    payer_name: str,
    payer_email: str,
) -> str:
    """
    Jana HMAC SHA-256 Payment Intent.

    Field disusun mengikut nama:
    amount, order_number, payer_email,
    payer_name, payment_channel.
    """

    payload = {
        "payment_channel": (
            format_checksum_payment_channel(
                payment_channels
            )
        ),
        "order_number": order_number,
        "amount": f"{amount:.2f}",
        "payer_name": payer_name,
        "payer_email": payer_email,
    }

    sorted_values = [
        str(
            payload[key]
        )
        for key in sorted(
            payload
        )
    ]

    payload_string = "|".join(
        sorted_values
    )

    return hmac.new(
        key=api_secret_key.encode(
            "utf-8"
        ),
        msg=payload_string.encode(
            "utf-8"
        ),
        digestmod=hashlib.sha256,
    ).hexdigest()


def extract_response_data(
    raw_payload: dict[str, Any],
) -> dict[str, Any]:
    """Dapatkan objek data daripada respons API."""

    raw_data = raw_payload.get(
        "data"
    )

    if isinstance(
        raw_data,
        dict,
    ):
        return raw_data

    return raw_payload


def extract_first_value(
    data: dict[str, Any],
    field_names: tuple[str, ...],
) -> Any:
    """Cari nilai pertama daripada beberapa nama field."""

    for field_name in field_names:
        value = data.get(
            field_name
        )

        if value is not None:
            return value

    return None


def parse_optional_decimal(
    value: Any,
) -> Decimal | None:
    """Tukar jumlah respons kepada Decimal."""

    if value is None:
        return None

    try:
        return Decimal(
            str(value)
        ).quantize(
            Decimal("0.01")
        )
    except (
        InvalidOperation,
        TypeError,
        ValueError,
    ):
        return None


class BayarCashClient:
    """HTTP adapter untuk BayarCash API v3."""

    def __init__(
        self,
        config: BayarCashConfig,
    ) -> None:
        self.config = config

        self._client = httpx.Client(
            base_url=(
                config.base_url.rstrip("/")
                + "/"
            ),
            timeout=config.timeout_seconds,
            headers={
                "Authorization": (
                    f"Bearer {config.api_token}"
                ),
                "Accept": "application/json",
                "Content-Type": "application/json",
                "User-Agent": (
                    "ReceiptBot/1.5 "
                    "BayarCashAdapter"
                ),
            },
        )

    def __enter__(
        self,
    ) -> "BayarCashClient":
        return self

    def __exit__(
        self,
        exc_type: object,
        exc_value: object,
        traceback: object,
    ) -> None:
        self.close()

    def close(self) -> None:
        """Tutup HTTP client."""

        self._client.close()

    def build_payment_intent_payload(
        self,
        request: BayarCashPaymentIntentRequest,
    ) -> dict[str, Any]:
        """Bina dan tandatangan payload Payment Intent."""

        order_number = normalize_order_number(
            request.order_number
        )

        amount = normalize_amount(
            request.amount
        )

        payer_name = normalize_payer_name(
            request.payer_name
        )

        payer_email = normalize_payer_email(
            request.payer_email
        )

        payer_phone = normalize_phone_number(
            request.payer_telephone_number
        )

        payment_channels = (
            normalize_payment_channels(
                raw_channels=(
                    request.payment_channel
                ),
                default_channel=(
                    self.config.payment_channel
                ),
            )
        )

        payload: dict[str, Any] = {
            "portal_key": (
                self.config.portal_key
            ),
            "payment_channel": (
                list(payment_channels)
                if len(payment_channels) > 1
                else payment_channels[0]
            ),
            "order_number": order_number,
            "amount": f"{amount:.2f}",
            "payer_name": payer_name,
            "payer_email": payer_email,
        }

        if payer_phone:
            payload[
                "payer_telephone_number"
            ] = payer_phone

        return_url = (
            request.return_url
            or self.config.return_url
        )

        callback_url = (
            request.callback_url
            or self.config.callback_url
        )

        if return_url:
            payload[
                "return_url"
            ] = return_url

        if callback_url:
            payload[
                "callback_url"
            ] = callback_url

        if request.metadata:
            payload[
                "metadata"
            ] = request.metadata

        payload[
            "checksum"
        ] = create_payment_intent_checksum(
            api_secret_key=(
                self.config.api_secret_key
            ),
            payment_channels=payment_channels,
            order_number=order_number,
            amount=amount,
            payer_name=payer_name,
            payer_email=payer_email,
        )

        return payload

    def create_payment_intent(
        self,
        request: BayarCashPaymentIntentRequest,
    ) -> BayarCashPaymentIntent:
        """Cipta Payment Intent melalui API BayarCash."""

        payload = (
            self.build_payment_intent_payload(
                request
            )
        )

        raw_response = self._request(
            method="POST",
            endpoint="payment-intents",
            json_payload=payload,
        )

        return self._parse_payment_intent(
            raw_response
        )

    def get_payment_intent(
        self,
        payment_intent_id: str,
    ) -> BayarCashPaymentIntent:
        """Dapatkan Payment Intent melalui ID."""

        normalized_id = (
            payment_intent_id.strip()
        )

        if not normalized_id:
            raise BayarCashValidationError(
                "Payment Intent ID diperlukan."
            )

        raw_response = self._request(
            method="GET",
            endpoint=(
                f"payment-intents/"
                f"{normalized_id}"
            ),
        )

        return self._parse_payment_intent(
            raw_response
        )

    def cancel_payment_intent(
        self,
        payment_intent_id: str,
    ) -> BayarCashPaymentIntent:
        """Batalkan Payment Intent BayarCash."""

        normalized_id = (
            payment_intent_id.strip()
        )

        if not normalized_id:
            raise BayarCashValidationError(
                "Payment Intent ID diperlukan."
            )

        raw_response = self._request(
            method="DELETE",
            endpoint=(
                f"payment-intents/"
                f"{normalized_id}"
            ),
        )

        return self._parse_payment_intent(
            raw_response
        )

    def get_portals(
        self,
    ) -> list[dict[str, Any]]:
        """Dapatkan portal milik merchant."""

        raw_response = self._request(
            method="GET",
            endpoint="portals",
        )

        data = raw_response.get(
            "data",
            raw_response,
        )

        if isinstance(
            data,
            list,
        ):
            return [
                item
                for item in data
                if isinstance(
                    item,
                    dict,
                )
            ]

        return []

    def _request(
        self,
        method: str,
        endpoint: str,
        json_payload: (
            dict[str, Any]
            | None
        ) = None,
    ) -> dict[str, Any]:
        """Hantar request dan map ralat API."""

        try:
            response = self._client.request(
                method=method,
                url=endpoint,
                json=json_payload,
            )

        except httpx.TimeoutException as error:
            raise BayarCashAPIError(
                "Permintaan ke BayarCash "
                "telah tamat masa."
            ) from error

        except httpx.RequestError as error:
            raise BayarCashAPIError(
                "BayarCash tidak dapat dihubungi."
            ) from error

        try:
            response_payload = response.json()

        except ValueError:
            response_payload = {
                "message": response.text,
            }

        if not isinstance(
            response_payload,
            dict,
        ):
            response_payload = {
                "data": response_payload,
            }

        if response.is_success:
            return response_payload

        message = extract_first_value(
            response_payload,
            (
                "message",
                "error",
                "detail",
            ),
        )

        error_message = str(
            message
            or "BayarCash memulangkan ralat."
        )

        if response.status_code in {
            401,
            403,
        }:
            raise BayarCashAuthenticationError(
                error_message
            )

        if response.status_code == 404:
            raise BayarCashNotFoundError(
                error_message
            )

        if response.status_code == 422:
            raise BayarCashValidationError(
                error_message
            )

        if response.status_code == 429:
            raise BayarCashRateLimitError(
                error_message
            )

        logger.error(
            "BayarCash API error. "
            "Status: %s | Respons: %s",
            response.status_code,
            response_payload,
        )

        raise BayarCashAPIError(
            f"BayarCash API gagal "
            f"({response.status_code}): "
            f"{error_message}"
        )

    def _parse_payment_intent(
        self,
        raw_payload: dict[str, Any],
    ) -> BayarCashPaymentIntent:
        """Tukar respons API kepada model dalaman."""

        data = extract_response_data(
            raw_payload
        )

        payment_intent_id = (
            extract_first_value(
                data,
                (
                    "id",
                    "payment_intent_id",
                    "payment_intent",
                ),
            )
        )

        checkout_url = (
            extract_first_value(
                data,
                (
                    "url",
                    "checkout_url",
                    "payment_url",
                    "redirect_url",
                ),
            )
        )

        if payment_intent_id is None:
            raise BayarCashAPIError(
                "Respons BayarCash tidak mempunyai "
                "Payment Intent ID."
            )

        if checkout_url is None:
            raise BayarCashAPIError(
                "Respons BayarCash tidak mempunyai "
                "checkout URL."
            )

        return BayarCashPaymentIntent(
            payment_intent_id=str(
                payment_intent_id
            ),
            order_number=(
                str(
                    data.get("order_number")
                )
                if data.get("order_number")
                is not None
                else None
            ),
            amount=parse_optional_decimal(
                data.get("amount")
            ),
            status=extract_first_value(
                data,
                (
                    "status",
                    "transaction_status",
                ),
            ),
            checkout_url=str(
                checkout_url
            ),
            raw_payload=raw_payload,
        )