import json
from pathlib import Path
from typing import Literal

from google import genai
from google.genai import types
from pydantic import BaseModel, Field

from config import GEMINI_API_KEY, GEMINI_MODEL


client = genai.Client(
    api_key=GEMINI_API_KEY,
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
    """Struktur tetap hasil bacaan AI."""

    is_receipt: bool = Field(
        description="True jika gambar ialah resit pembelian."
    )

    merchant: str = Field(
        description=(
            "Nama kedai atau merchant. "
            "Gunakan 'Tidak pasti' jika tidak jelas."
        )
    )

    receipt_date: str = Field(
        description=(
            "Tarikh dalam format YYYY-MM-DD. "
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
        description="Kategori perbelanjaan paling sesuai."
    )


def get_mime_type(image_path: Path) -> str:
    """Tentukan MIME type imej."""

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


def extract_receipt(
    image_path: Path,
) -> ReceiptData:
    """Baca gambar resit menggunakan Gemini."""

    if not image_path.exists():
        raise FileNotFoundError(
            f"Fail gambar tidak dijumpai: {image_path}"
        )

    image_bytes = image_path.read_bytes()
    mime_type = get_mime_type(image_path)

    prompt = """
Anda ialah pembaca resit untuk home bakery dan
small business di Malaysia.

Analisis gambar ini dengan teliti.

Tugas:
1. Tentukan sama ada gambar ini ialah resit.
2. Kenal pasti nama kedai.
3. Kenal pasti tarikh transaksi.
4. Kenal pasti jumlah akhir yang dibayar.
5. Pilih kategori paling sesuai.

Kategori dibenarkan:
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
- Tarikh mesti dalam format YYYY-MM-DD.
- Jika merchant tidak jelas, guna "Tidak pasti".
- Jika tarikh tidak jelas, guna "Tidak pasti".
- Jika jumlah tidak jelas, guna 0.
- Jika gambar bukan resit, is_receipt mesti false.
"""

    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=[
            prompt,
            types.Part.from_bytes(
                data=image_bytes,
                mime_type=mime_type,
            ),
        ],
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_json_schema=(
                ReceiptData.model_json_schema()
            ),
            temperature=0,
        ),
    )

    if not response.text:
        raise RuntimeError(
            "Gemini tidak memulangkan respons teks."
        )

    try:
        raw_data = json.loads(response.text)
    except json.JSONDecodeError as error:
        raise RuntimeError(
            f"Respons Gemini bukan JSON sah: {response.text}"
        ) from error

    return ReceiptData.model_validate(raw_data)