from __future__ import annotations

import re
import unicodedata

NORMALIZATION_VERSION = "document-normalization-v1"


def normalize_text(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value.casefold())
    plain = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    plain = plain.translate(str.maketrans({"ł": "l", "đ": "d", "ø": "o"}))
    plain = re.sub(r"[^\w]+", " ", plain, flags=re.UNICODE)
    return " ".join(plain.split())


def subject_key(category: str, value: str) -> tuple[str, str]:
    return category, " ".join(unicodedata.normalize("NFKC", value).casefold().split())
