import base64
import logging
from pathlib import Path
from typing import Literal

from openai import OpenAI
from pydantic import BaseModel, Field

from config import (
    OPENAI_API_KEY,
    OPENAI_MODEL,
)


logger = logging.getLogger(__name__)


client = OpenAI(
    api_key=OPENAI_API_KEY,
    timeout=30.0,
    max_retries=1,
)


ReceiptCategory = Literal[
    "Bahan Mentah",
    "Packaging",
    "Peralatan",
    "Penghantaran",
    "Pemasaran",
    "Utiliti",
    "Sewa",
    "Lain-lain",
]


class ReceiptData(BaseModel):
    """Struktur tetap hasil bacaan resit."""

    is_receipt: bool = Field(
        description=(
            "True jika gambar ialah resit pembelian."
        )
    )

    merchant: str = Field(
        description=(
            "Nama kedai atau merchant. "
            "Gunakan 'Tidak pasti' jika tidak jelas."
        )
    )

    receipt_date: str = Field(
        description=(
            "Tarikh transaksi dalam format YYYY-MM-DD. "
            "Gunakan 'Tidak pasti' jika tidak jelas."
        )
    )

    total: float = Field(
        description=(
            "Jumlah akhir yang dibayar. "
            "Gunakan 0 jika tidak jelas."
        )
    )

    category: ReceiptCategory = Field(
        description=(
            "Kategori perbelanjaan yang paling sesuai."
        )
    )


def get_mime_type(
    image_path: Path,
) -> str:
    """Tentukan MIME type berdasarkan extension."""

    extension = image_path.suffix.lower()

    mime_types = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
        ".heic": "image/heic",
        ".heif": "image/heif",
    }

    return mime_types.get(
        extension,
        "image/jpeg",
    )


def encode_image(
    image_path: Path,
) -> str:
    """Tukar imej kepada Base64."""

    with image_path.open("rb") as image_file:
        return base64.b64encode(
            image_file.read()
        ).decode("utf-8")


def build_prompt() -> str:
    """Bina arahan tetap untuk pembacaan resit."""

    return """
Baca gambar resit ini dengan teliti.

Ekstrak:
1. Sama ada gambar benar-benar resit.
2. Nama kedai atau merchant.
3. Tarikh transaksi.
4. Jumlah akhir yang dibayar.
5. Kategori perbelanjaan.

Kategori yang dibenarkan:
- Bahan Mentah
- Packaging
- Peralatan
- Penghantaran
- Pemasaran
- Utiliti
- Sewa
- Lain-lain

Peraturan:
- Jangan mereka-reka maklumat.
- Semak digit tahun dengan sangat teliti.
- Tarikh mesti dalam format YYYY-MM-DD.
- Jika nama kedai tidak jelas, guna "Tidak pasti".
- Jika tarikh tidak jelas, guna "Tidak pasti".
- Jika jumlah tidak jelas, guna 0.
- Gunakan jumlah akhir selepas cukai atau diskaun.
- Jika gambar bukan resit, is_receipt mesti false.
""".strip()


def extract_receipt(
    image_path: Path,
) -> ReceiptData:
    """Baca gambar resit menggunakan OpenAI Vision."""

    if not image_path.exists():
        raise FileNotFoundError(
            f"Fail gambar tidak dijumpai: {image_path}"
        )

    base64_image = encode_image(
        image_path
    )

    mime_type = get_mime_type(
        image_path
    )

    data_url = (
        f"data:{mime_type};base64,{base64_image}"
    )

    logger.info(
        "Menghantar gambar ke OpenAI. "
        "Model: %s | Saiz: %s bytes",
        OPENAI_MODEL,
        image_path.stat().st_size,
    )

    try:
        response = client.responses.parse(
            model=OPENAI_MODEL,
            input=[
                {
                    "role": "system",
                    "content": (
                        "Anda ialah sistem pembaca resit "
                        "untuk home bakery dan small "
                        "business di Malaysia. "
                        "Utamakan ketepatan merchant, "
                        "tarikh dan jumlah akhir."
                    ),
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": build_prompt(),
                        },
                        {
                            "type": "input_image",
                            "image_url": data_url,
                            "detail": "high",
                        },
                    ],
                },
            ],
            text_format=ReceiptData,
            max_output_tokens=300,
        )

    except Exception as error:
        logger.exception(
            "OpenAI gagal memproses gambar: %s",
            error,
        )

        raise RuntimeError(
            "OpenAI gagal membaca resit."
        ) from error

    receipt_data = response.output_parsed

    if receipt_data is None:
        logger.error(
            "OpenAI tidak memulangkan structured output. "
            "Response ID: %s",
            response.id,
        )

        raise RuntimeError(
            "OpenAI tidak memulangkan data resit."
        )

    logger.info(
        "Respons OpenAI diterima. "
        "Merchant: %s | Tarikh: %s | Jumlah: %.2f",
        receipt_data.merchant,
        receipt_data.receipt_date,
        receipt_data.total,
    )

    return receipt_data