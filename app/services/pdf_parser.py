import re
from dataclasses import dataclass

import pdfplumber


class PDFParseError(Exception):
    pass


@dataclass
class TransaccionExtraida:
    fecha: str
    descripcion: str
    monto: float
    numero_tarjeta: str | None = None
    moneda: str = "ARS"
    tipo_tarjeta: str = "DESCONOCIDO"
    cantidad_cuotas: int | None = None
    cuotas_faltantes: int | None = None
    cuota_numero: int | None = None


class ResumenParser:

    @staticmethod
    def detectar_tipo(file_path: str) -> str:
        """Detecta tipo de tarjeta por keywords en el PDF. No falla nunca."""
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages[:3]:
                text = page.extract_text() or ""
                text_lower = text.lower()
                if "american express" in text_lower or "amex" in text_lower:
                    return "AMEX"
                if "visa" in text_lower:
                    return "VISA"
                if "mastercard" in text_lower or "master card" in text_lower:
                    return "MASTERCARD"
        return "DESCONOCIDO"

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
                try:
                    result_str = llm_router.extract_with_vision(images)
                except Exception:
                    result_str = ""
                if result_str:
                    import json
                    import re
                    json_match = re.search(r'```(?:json)?\s*([\s\S]*?)```', result_str)
                    if json_match:
                        result_str = json_match.group(1).strip()
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
                            fecha = item.get("fecha", item.get("date", ""))
                            descripcion = item.get("descripcion", item.get("description", ""))
                            moneda = item.get("moneda", item.get("currency", "ARS"))
                            try:
                                monto_raw = item.get("monto", item.get("amount", 0))
                                if isinstance(monto_raw, str):
                                    monto_raw = monto_raw.replace(".", "").replace(",", ".").replace("CR", "").replace("DB", "").strip()
                                monto = float(monto_raw)
                            except (ValueError, TypeError):
                                continue
                            result.append(TransaccionExtraida(
                                fecha=fecha,
                                descripcion=descripcion,
                                monto=monto,
                                numero_tarjeta=item.get("numero_tarjeta", item.get("card", None)),
                                moneda=moneda,
                                tipo_tarjeta=item.get("tipo_tarjeta", "DESCONOCIDO"),
                                cantidad_cuotas=item.get("cantidad_cuotas"),
                                cuotas_faltantes=item.get("cuotas_faltantes"),
                                cuota_numero=item.get("cuota_numero"),
                            ))
                        if result:
                            return result
                    except (json.JSONDecodeError, ValueError, TypeError):
                        pass
        return []
