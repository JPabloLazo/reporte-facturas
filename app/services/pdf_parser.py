import re
from enum import Enum
from dataclasses import dataclass

import pdfplumber


class PDFParseError(Exception):
    pass


class TipoResumen(Enum):
    AMEX = "AMEX"
    VISA = "VISA"


@dataclass
class TransaccionExtraida:
    fecha: str
    descripcion: str
    monto: float
    numero_tarjeta: str | None = None
    moneda: str = "ARS"


class ResumenParser:

    @staticmethod
    def detectar_tipo(file_path: str) -> TipoResumen:
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages[:3]:
                text = page.extract_text() or ""
                text_lower = text.lower()
                if "american express" in text_lower or "amex" in text_lower:
                    return TipoResumen.AMEX
                if "visa" in text_lower:
                    return TipoResumen.VISA
        raise ValueError("Tipo de resumen no reconocido")

    @staticmethod
    def _parse_amount(value: str) -> float:
        cleaned = value.replace("$", "").replace("U$S", "").replace(" ", "").strip()
        if cleaned.startswith("(") and cleaned.endswith(")"):
            cleaned = "-" + cleaned[1:-1]
        if "," in cleaned and "." in cleaned:
            if cleaned.rindex(",") > cleaned.rindex("."):
                cleaned = cleaned.replace(".", "").replace(",", ".")
            else:
                cleaned = cleaned.replace(",", "")
        elif "," in cleaned:
            cleaned = cleaned.replace(",", ".")
        return float(cleaned)

    @staticmethod
    def _normalize_fecha(raw: str) -> str:
        cleaned = raw.strip()
        match = re.match(r'(\d{1,2})/(\d{1,2})/(\d{2,4})', cleaned)
        if match:
            d, m, y = match.groups()
            if len(y) == 2:
                y = f"20{y}"
            return f"{d.zfill(2)}/{m.zfill(2)}/{y}"
        match = re.match(r'(\d{1,2})-(\d{1,2})-(\d{2,4})', cleaned)
        if match:
            d, m, y = match.groups()
            if len(y) == 2:
                y = f"20{y}"
            return f"{d.zfill(2)}/{m.zfill(2)}/{y}"
        return cleaned

    @staticmethod
    def extraer_numero_tarjeta(text: str) -> str | None:
        pattern = r'(?:\d{4}[-\s]?){3}(\d{4})'
        match = re.search(pattern, text)
        if match:
            return f"****{match.group(1)}"
        pattern2 = r'(?:terminada\s*en|nro[.:\s]*|tarjeta[:\s]*)\**(\d{4})'
        match2 = re.search(pattern2, text, re.IGNORECASE)
        if match2:
            return f"****{match2.group(1)}"
        return None

    @staticmethod
    def parsear_fallback_vision(images: list[str], llm_router=None) -> list[TransaccionExtraida]:
        if llm_router is not None and hasattr(llm_router, "extract_with_vision"):
            if images:
                result_str = llm_router.extract_with_vision(images)
                if result_str:
                    import json
                    try:
                        data = json.loads(result_str)
                        if isinstance(data, list):
                            items = data
                        elif isinstance(data, dict):
                            items = data.get("transacciones", data.get("transactions", []))
                        else:
                            items = []
                        result = []
                        for item in items:
                            result.append(TransaccionExtraida(
                                fecha=item.get("fecha", ""),
                                descripcion=item.get("descripcion", item.get("description", "")),
                                monto=float(item.get("monto", item.get("amount", 0))),
                                numero_tarjeta=item.get("numero_tarjeta", item.get("card", None)),
                                moneda=item.get("moneda", item.get("currency", "ARS")),
                            ))
                        if result:
                            return result
                    except (json.JSONDecodeError, ValueError, TypeError):
                        pass
        return []
