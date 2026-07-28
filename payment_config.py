import os
from dataclasses import dataclass
from enum import StrEnum

from dotenv import load_dotenv


load_dotenv()


class BayarCashEnvironment(StrEnum):
    """Environment rasmi BayarCash."""

    SANDBOX = "SANDBOX"
    PRODUCTION = "PRODUCTION"


class PaymentConfigurationError(
    RuntimeError
):
    """Konfigurasi payment gateway tidak lengkap."""


BAYARCASH_SANDBOX_BASE_URL = (
    "https://api.console."
    "bayarcash-sandbox.com/v3"
)

BAYARCASH_PRODUCTION_BASE_URL = (
    "https://api.console.bayar.cash/v3"
)


@dataclass(
    frozen=True,
    slots=True,
)
class BayarCashConfig:
    """Konfigurasi lengkap BayarCash."""

    environment: BayarCashEnvironment

    api_token: str
    api_secret_key: str
    portal_key: str

    base_url: str
    payment_channel: int

    callback_url: str | None
    return_url: str | None

    timeout_seconds: float = 30.0

    @property
    def is_sandbox(self) -> bool:
        """Semak sama ada adapter menggunakan sandbox."""

        return (
            self.environment
            == BayarCashEnvironment.SANDBOX
        )

    @property
    def is_production(self) -> bool:
        """Semak sama ada adapter menggunakan production."""

        return (
            self.environment
            == BayarCashEnvironment.PRODUCTION
        )


def get_optional_environment_value(
    variable_name: str,
) -> str | None:
    """Baca nilai pilihan daripada environment."""

    raw_value = os.getenv(
        variable_name
    )

    if raw_value is None:
        return None

    normalized_value = raw_value.strip()

    if not normalized_value:
        return None

    return normalized_value


def get_required_environment_value(
    variable_name: str,
) -> str:
    """Baca nilai wajib daripada environment."""

    value = get_optional_environment_value(
        variable_name
    )

    if value is None:
        raise PaymentConfigurationError(
            f"{variable_name} tidak dijumpai "
            "atau masih kosong dalam fail .env."
        )

    return value


def parse_bayarcash_environment(
    raw_environment: str,
) -> BayarCashEnvironment:
    """Sahkan environment BayarCash."""

    normalized_environment = (
        raw_environment.strip().upper()
    )

    try:
        return BayarCashEnvironment(
            normalized_environment
        )

    except ValueError as error:
        raise PaymentConfigurationError(
            "BAYARCASH_ENVIRONMENT tidak sah. "
            "Gunakan SANDBOX atau PRODUCTION."
        ) from error


def parse_payment_channel(
    raw_channel: str,
) -> int:
    """Sahkan nombor payment channel BayarCash."""

    try:
        payment_channel = int(
            raw_channel.strip()
        )

    except (
        TypeError,
        ValueError,
    ) as error:
        raise PaymentConfigurationError(
            "BAYARCASH_PAYMENT_CHANNEL "
            "mestilah nombor."
        ) from error

    if payment_channel <= 0:
        raise PaymentConfigurationError(
            "BAYARCASH_PAYMENT_CHANNEL "
            "mestilah lebih besar daripada sifar."
        )

    return payment_channel


def resolve_bayarcash_base_url(
    environment: BayarCashEnvironment,
    configured_base_url: str | None,
) -> str:
    """Tentukan base URL mengikut environment."""

    if configured_base_url:
        return configured_base_url.rstrip(
            "/"
        )

    if (
        environment
        == BayarCashEnvironment.SANDBOX
    ):
        return BAYARCASH_SANDBOX_BASE_URL

    return BAYARCASH_PRODUCTION_BASE_URL


def validate_environment_base_url(
    environment: BayarCashEnvironment,
    base_url: str,
) -> None:
    """
    Elakkan credential production dihantar secara
    tidak sengaja ke sandbox atau sebaliknya.
    """

    normalized_url = base_url.lower()

    if (
        environment
        == BayarCashEnvironment.SANDBOX
        and "sandbox" not in normalized_url
    ):
        raise PaymentConfigurationError(
            "BAYARCASH_ENVIRONMENT ialah SANDBOX "
            "tetapi BAYARCASH_BASE_URL bukan "
            "alamat sandbox."
        )

    if (
        environment
        == BayarCashEnvironment.PRODUCTION
        and "sandbox" in normalized_url
    ):
        raise PaymentConfigurationError(
            "BAYARCASH_ENVIRONMENT ialah PRODUCTION "
            "tetapi BAYARCASH_BASE_URL menggunakan "
            "alamat sandbox."
        )

    if not normalized_url.startswith(
        "https://"
    ):
        raise PaymentConfigurationError(
            "BAYARCASH_BASE_URL wajib menggunakan HTTPS."
        )


def load_bayarcash_config() -> BayarCashConfig:
    """Baca dan sahkan konfigurasi BayarCash."""

    environment = parse_bayarcash_environment(
        os.getenv(
            "BAYARCASH_ENVIRONMENT",
            "SANDBOX",
        )
    )

    configured_base_url = (
        get_optional_environment_value(
            "BAYARCASH_BASE_URL"
        )
    )

    base_url = resolve_bayarcash_base_url(
        environment=environment,
        configured_base_url=(
            configured_base_url
        ),
    )

    validate_environment_base_url(
        environment=environment,
        base_url=base_url,
    )

    raw_timeout = os.getenv(
        "BAYARCASH_TIMEOUT_SECONDS",
        "30",
    )

    try:
        timeout_seconds = float(
            raw_timeout
        )
    except ValueError as error:
        raise PaymentConfigurationError(
            "BAYARCASH_TIMEOUT_SECONDS "
            "mestilah nombor."
        ) from error

    if timeout_seconds <= 0:
        raise PaymentConfigurationError(
            "BAYARCASH_TIMEOUT_SECONDS "
            "mestilah lebih besar daripada sifar."
        )

    return BayarCashConfig(
        environment=environment,
        api_token=(
            get_required_environment_value(
                "BAYARCASH_API_TOKEN"
            )
        ),
        api_secret_key=(
            get_required_environment_value(
                "BAYARCASH_API_SECRET_KEY"
            )
        ),
        portal_key=(
            get_required_environment_value(
                "BAYARCASH_PORTAL_KEY"
            )
        ),
        base_url=base_url,
        payment_channel=(
            parse_payment_channel(
                os.getenv(
                    "BAYARCASH_PAYMENT_CHANNEL",
                    "1",
                )
            )
        ),
        callback_url=(
            get_optional_environment_value(
                "BAYARCASH_CALLBACK_URL"
            )
        ),
        return_url=(
            get_optional_environment_value(
                "BAYARCASH_RETURN_URL"
            )
        ),
        timeout_seconds=timeout_seconds,
    )


def describe_bayarcash_config(
    config: BayarCashConfig,
) -> str:
    """
    Paparkan konfigurasi tanpa mendedahkan
    token atau secret key.
    """

    callback_status = (
        "DIISI"
        if config.callback_url
        else "KOSONG"
    )

    return_status = (
        "DIISI"
        if config.return_url
        else "KOSONG"
    )

    return (
        f"Environment: {config.environment.value}\n"
        f"Base URL: {config.base_url}\n"
        f"Payment Channel: "
        f"{config.payment_channel}\n"
        f"API Token: DIISI\n"
        f"API Secret Key: DIISI\n"
        f"Portal Key: DIISI\n"
        f"Callback URL: {callback_status}\n"
        f"Return URL: {return_status}"
    )